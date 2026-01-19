# Docker Compose Deployment

## Files to Modify/Create
- `deployment/docker-compose.yml` (new)
- `deployment/icecast/icecast.xml` (new - Icecast config)
- `deployment/caddy/Caddyfile` (new - reverse proxy config)
- `deployment/.env.example` (new - environment variables template)
- `deployment/README.md` (new - deployment instructions)

## Implementation Details

Package the entire radio system for deployment on Raspberry Pi using Docker Compose.

### Docker Compose Configuration

```yaml
# deployment/docker-compose.yml
version: '3.8'

services:
  # ===== Icecast Streaming Server =====
  icecast:
    image: infiniteproject/icecast
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./icecast/icecast.xml:/etc/icecast.xml:ro
    environment:
      - ICECAST_SOURCE_PASSWORD=${ICECAST_PASSWORD:-hackme}
      - ICECAST_ADMIN_PASSWORD=${ICECAST_ADMIN_PASSWORD:-admin}
      - ICECAST_RELAY_PASSWORD=${ICECAST_RELAY_PASSWORD:-relay}
    networks:
      - radio

  # ===== Liquidsoap Audio Engine =====
  liquidsoap:
    build: ./liquidsoap
    restart: unless-stopped
    depends_on:
      - icecast
      - backend
    volumes:
      - ${MUSIC_DIR:-/music}:/music:ro
      - ./liquidsoap/radio.liq:/etc/liquidsoap/radio.liq:ro
      - liquidsoap_logs:/var/log/liquidsoap
    networks:
      - radio

  # ===== FastAPI Backend =====
  backend:
    build:
      context: ../
      dockerfile: deployment/backend/Dockerfile
    restart: unless-stopped
    volumes:
      - ../src:/app/src:ro  # Mount source code
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - MUSIC_DIR=${MUSIC_DIR:-/music}
    ports:
      - "8001:8000"  # Internal port for debugging
    networks:
      - radio

  # ===== React Frontend =====
  frontend:
    build:
      context: ../web/frontend
      dockerfile: ../../deployment/frontend/Dockerfile
    restart: unless-stopped
    depends_on:
      - backend
    networks:
      - radio

  # ===== Caddy Reverse Proxy =====
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - radio

networks:
  radio:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
  liquidsoap_logs:
```

### Icecast Configuration

```xml
<!-- deployment/icecast/icecast.xml -->
<icecast>
    <location>Earth</location>
    <admin>admin@example.com</admin>

    <limits>
        <clients>100</clients>
        <sources>2</sources>
        <queue-size>524288</queue-size>
        <client-timeout>30</client-timeout>
        <header-timeout>15</header-timeout>
        <source-timeout>10</source-timeout>
        <burst-on-connect>1</burst-on-connect>
        <burst-size>65535</burst-size>
    </limits>

    <authentication>
        <source-password>hackme</source-password>
        <relay-password>relay</relay-password>
        <admin-user>admin</admin-user>
        <admin-password>admin</admin-password>
    </authentication>

    <hostname>mm.kevinandrews.info</hostname>

    <listen-socket>
        <port>8000</port>
    </listen-socket>

    <mount>
        <mount-name>/stream</mount-name>
        <fallback-mount>/silence.opus</fallback-mount>
        <fallback-override>1</fallback-override>
        <charset>UTF-8</charset>
    </mount>

    <fileserve>1</fileserve>

    <paths>
        <basedir>/usr/share/icecast</basedir>
        <logdir>/var/log/icecast</logdir>
        <webroot>/usr/share/icecast/web</webroot>
        <adminroot>/usr/share/icecast/admin</adminroot>
        <alias source="/" destination="/status.xsl"/>
    </paths>

    <logging>
        <accesslog>access.log</accesslog>
        <errorlog>error.log</errorlog>
        <loglevel>3</loglevel>
    </logging>

    <security>
        <chroot>0</chroot>
    </security>
</icecast>
```

### Caddy Reverse Proxy

```caddyfile
# deployment/caddy/Caddyfile
mm.kevinandrews.info {
    # Frontend (React SPA)
    handle / {
        reverse_proxy frontend:3000
    }

    # Backend API
    handle /api/* {
        reverse_proxy backend:8000
    }

    # WebSocket
    handle /api/radio/live {
        reverse_proxy backend:8000 {
            header_up Upgrade {http.request.header.Upgrade}
            header_up Connection {http.request.header.Connection}
        }
    }

    # Icecast stream
    handle /stream {
        reverse_proxy icecast:8000
    }

    # Icecast stats
    handle /status* {
        reverse_proxy icecast:8000
    }

    # Enable HTTPS with automatic cert from Let's Encrypt
    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }

    # Logs
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

### Backend Dockerfile

```dockerfile
# deployment/backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src ./src

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8000

# Run FastAPI server
CMD ["uv", "run", "uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
# deployment/frontend/Dockerfile
FROM node:20-slim AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

# Build for production
RUN npm run build

# Production image
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config for SPA
RUN echo 'server { \
    listen 3000; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### Environment Variables

```bash
# deployment/.env.example
# Copy to .env and fill in values

# PostgreSQL (hosted)
DATABASE_URL=postgresql://user:password@host:5432/music_minion

# Icecast passwords
ICECAST_PASSWORD=hackme
ICECAST_ADMIN_PASSWORD=admin
ICECAST_RELAY_PASSWORD=relay

# Music directory (synced via Syncthing)
MUSIC_DIR=/home/pi/music-radio

# Cloudflare API token for HTTPS (optional)
CLOUDFLARE_API_TOKEN=your_token_here
```

### Deployment Instructions

```markdown
# deployment/README.md

# Raspberry Pi Deployment

## Prerequisites

1. Raspberry Pi 4/5 with 128GB SD card
2. Raspbian OS installed
3. Docker and Docker Compose installed
4. Domain name pointing to Pi's IP (mm.kevinandrews.info)
5. PostgreSQL database hosted externally

## Setup

1. **Clone repository:**
   ```bash
   git clone https://github.com/yourusername/music-minion.git
   cd music-minion/deployment
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   nano .env  # Fill in DATABASE_URL and passwords
   ```

3. **Set up music sync:**
   - Install Syncthing: `sudo apt install syncthing`
   - Configure sync folder at `/home/pi/music-radio`
   - Point MUSIC_DIR in .env to this folder

4. **Build and start services:**
   ```bash
   docker compose build
   docker compose up -d
   ```

5. **Verify services:**
   ```bash
   docker compose ps  # All should show "Up"
   docker compose logs liquidsoap  # Check for errors
   ```

6. **Test stream:**
   ```bash
   mpv http://localhost:8000/stream
   ```

## Maintenance

**View logs:**
```bash
docker compose logs -f [service_name]
```

**Restart services:**
```bash
docker compose restart [service_name]
```

**Update code:**
```bash
git pull
docker compose build
docker compose up -d
```

**Rebuild schedule:**
Visit: http://mm.kevinandrews.info/api/radio/stations/1/activate
```

## Acceptance Criteria

- [ ] All services start successfully via `docker compose up`
- [ ] Icecast stream accessible at `http://localhost:8000/stream`
- [ ] Backend API responds at `http://localhost:8001/api/radio/stations`
- [ ] Frontend accessible at `http://localhost:80`
- [ ] Caddy serves HTTPS with auto-renewed Let's Encrypt cert
- [ ] Services auto-restart on crash (`restart: unless-stopped`)
- [ ] Music directory mounted read-only in Liquidsoap
- [ ] Logs persisted in named volumes

## Dependencies

- Requires: **All previous tasks** (complete radio implementation)

## Testing

```bash
# Start services
cd deployment
docker compose up -d

# Check health
curl http://localhost:8001/api/radio/stations
curl http://localhost:8000/status.xsl

# Listen to stream
mpv http://localhost:8000/stream

# Check logs
docker compose logs -f liquidsoap

# Stop services
docker compose down
```
