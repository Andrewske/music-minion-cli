# Syncthing Setup Guide for Music Minion

**Purpose**: Sync music library between Linux (Music Minion curation) and Windows (Serato DJing)

**Last Updated**: 2025-09-29

---

## Overview

Syncthing provides bidirectional file synchronization between your Linux machine (where you curate music with Music Minion) and Windows machine (where you DJ with Serato). Changes to file metadata and playlists flow automatically in both directions.

**Two folders to sync**:
1. **Music Library** - Audio files with metadata
2. **Playlists** - Exported M3U8 and Serato .crate files

### What Gets Synced
- MP3/M4A audio files
- File metadata (ID3 tags, comments)
- Music Minion tags in COMMENT field
- Exported playlists (M3U8 and Serato .crate files)
- File modifications from either side

### Workflow
1. **Linux**: Curate music in Music Minion, add tags, create playlists
2. **Auto-sync**: Music Minion writes tags to file metadata
3. **Auto-export**: Playlists exported to M3U8/crate formats
4. **Syncthing**: Syncs files and playlists to Windows
5. **Windows**: View/edit tags and playlists in Serato
6. **Syncthing**: Syncs changes back to Linux
7. **Auto-sync**: Music Minion imports changes on startup

---

## Installation

### Linux Installation

#### Option 1: Package Manager (Recommended)

**Arch Linux**:
```bash
sudo pacman -S syncthing
```

**Ubuntu/Debian**:
```bash
sudo apt install syncthing
```

**Fedora**:
```bash
sudo dnf install syncthing
```

#### Option 2: Official Repository (Latest Version)

Add Syncthing repository:
```bash
# Add GPG key
curl -s https://syncthing.net/release-key.txt | sudo apt-key add -

# Add repository
echo "deb https://apt.syncthing.net/ syncthing stable" | sudo tee /etc/apt/sources.list.d/syncthing.list

# Install
sudo apt update
sudo apt install syncthing
```

#### Enable and Start Service

**User service** (runs when you're logged in):
```bash
systemctl --user enable syncthing.service
systemctl --user start syncthing.service
```

**System service** (runs at boot):
```bash
sudo systemctl enable syncthing@yourusername.service
sudo systemctl start syncthing@yourusername.service
```

**Recommended**: Use user service for desktop machines.

#### Verify Installation
```bash
systemctl --user status syncthing.service
```

You should see "active (running)".

---

### Windows Installation

#### Download and Install

1. **Download**: Visit https://syncthing.net/downloads/
2. **Choose**: "Windows (64-bit)" - Download the installer
3. **Run**: `syncthing-windows-amd64-v1.x.x-setup.exe`
4. **Install**: Follow the installer wizard (default options are fine)

#### Alternative: Portable Version

If you prefer not to install:
1. Download "Windows (64-bit)" ZIP file
2. Extract to a folder (e.g., `C:\Syncthing`)
3. Run `syncthing.exe`
4. Add to startup folder for auto-run

#### Enable Auto-Start

**Option 1: Windows Installer** (already configured)
- The installer adds Syncthing to startup automatically

**Option 2: Manual startup** (portable version)
1. Press `Win+R`, type `shell:startup`, press Enter
2. Create shortcut to `syncthing.exe` in this folder

#### Verify Installation

1. Syncthing should start automatically or run `syncthing.exe`
2. System tray icon appears (folder with green checkmark)
3. Web UI opens at http://localhost:8384

---

## Initial Configuration

### Linux Configuration

1. **Open Web UI**: http://localhost:8384
   - Should open automatically when service starts
   - If not, manually navigate in browser

2. **Set Device Name**:
   - Settings → General → Device Name
   - Example: "Linux-Laptop" or "Studio-PC"

3. **Configure Default Folder** (optional):
   - By default, Syncthing creates `~/Sync` folder
   - You can remove this if you only want to sync Music

4. **Security** (Important):
   - Settings → GUI
   - Set GUI Authentication Username/Password
   - Or bind to localhost only (default, safest for single-user)

### Windows Configuration

1. **Open Web UI**: http://localhost:8384
   - Opens automatically after installation
   - System tray icon → "Open Web UI"

2. **Set Device Name**:
   - Settings → General → Device Name
   - Example: "Windows-DJ" or "DJ-Laptop"

3. **Configure Default Folder** (optional):
   - Remove default sync folder if not needed

4. **Security**:
   - Same as Linux - set GUI password or keep localhost-only

---

## Connect Devices

### Get Device IDs

**Linux**:
1. Open Web UI: http://localhost:8384
2. Actions → Show ID
3. Copy the Device ID (long alphanumeric string)
4. QR code is also displayed for easy mobile connection

**Windows**:
1. Open Web UI: http://localhost:8384
2. Actions → Show ID
3. Copy the Device ID

### Add Remote Device

**On Linux** (to add Windows machine):
1. Click "Add Remote Device" (bottom right)
2. **Device ID**: Paste Windows device ID
3. **Device Name**: Enter recognizable name (e.g., "Windows-DJ")
4. **Sharing** tab: Don't select any folders yet
5. Click "Save"

**On Windows** (to add Linux machine):
1. Click "Add Remote Device"
2. **Device ID**: Paste Linux device ID
3. **Device Name**: Enter recognizable name (e.g., "Linux-Laptop")
4. **Sharing** tab: Don't select any folders yet
5. Click "Save"

### Accept Connection

After adding devices, each side will prompt:
- "Device 'Name' wants to connect. Add this device?"
- Click "Add Device" on both machines

You should see:
- Device status changes from "Disconnected" to "Connected"
- Green checkmark appears on device card

---

## Setup Music Library Sync

### On Linux (Share Music Folder)

1. **Add Folder**: Click "Add Folder" (bottom right)

2. **General Tab**:
   - **Folder Label**: "Music Library" (or any name you prefer)
   - **Folder Path**: `/home/yourusername/Music` (your library location)
   - **Folder Type**: "Send & Receive" (bidirectional sync)

3. **Sharing Tab**:
   - Check the box next to your Windows device
   - This shares the folder with Windows

4. **File Versioning** (Recommended):
   - **File Versioning**: Select "Simple File Versioning"
   - **Keep Versions**: 5 (keeps last 5 versions of changed files)
   - **Reason**: Protects against accidental deletions or corruption

5. **Ignore Patterns** (Optional):
   - Add patterns to exclude files:
     ```
     .DS_Store
     Thumbs.db
     *.tmp
     *.part
     desktop.ini
     .sync*
     ```

6. **Advanced Tab**:
   - **Scan Interval**: 60 seconds (default is fine)
   - **Watch for Changes**: Enable (faster sync)
   - **Send/Receive Limits**: Leave default unless bandwidth is limited

7. Click "Save"

### On Windows (Accept Shared Folder)

1. Windows should show notification: "Linux-Laptop wants to share folder 'Music Library'"

2. Click notification or go to Web UI

3. **Accept Prompt**:
   - Click "Add"

4. **Configure Folder Path**:
   - **Folder Path**: `C:\Users\YourName\Music` (or desired location)
   - **Important**: This is where synced files will appear

5. **Folder Type**:
   - Should be "Send & Receive" (bidirectional)

6. **File Versioning** (Recommended):
   - Enable same as Linux (Simple, keep 5 versions)

7. Click "Save"

### Verify Sync

After configuration:

1. **Check Status**:
   - Both machines show folder status
   - "Up to Date" when sync complete
   - Progress bar shows during sync

2. **Test Sync**:
   - Linux: Add a test file to `~/Music`
   - Windows: Check if file appears in `C:\Users\YourName\Music`
   - Windows: Modify file
   - Linux: Check if changes sync back

---

## Setup Playlists Sync

### Why Sync Playlists

Music Minion can export playlists to M3U8 and Serato .crate formats. Syncing the playlists folder allows:
- Serato on Windows to read playlists created in Music Minion
- Changes to playlists (adding/removing tracks) sync automatically
- Seamless DJ workflow with curated playlists

### On Linux (Share Playlists Folder)

1. **Determine Playlist Export Location**:

   Check Music Minion config: `~/.config/music-minion/config.toml`
   ```toml
   [playlists]
   export_path = "/home/yourusername/Music/Playlists"  # Your export location
   ```

   Default is typically `~/Music/Playlists` or `~/.local/share/music-minion/playlists`

2. **Add Folder**: Click "Add Folder" (bottom right)

3. **General Tab**:
   - **Folder Label**: "Music Minion Playlists"
   - **Folder Path**: `/home/yourusername/Music/Playlists` (or your export_path)
   - **Folder Type**: "Send & Receive" (bidirectional sync)

4. **Sharing Tab**:
   - Check the box next to your Windows device

5. **File Versioning** (Recommended):
   - **File Versioning**: Select "Simple File Versioning"
   - **Keep Versions**: 3 (playlists change frequently)
   - **Reason**: Protects against accidental playlist overwrites

6. **Ignore Patterns** (Optional):
   ```
   .DS_Store
   Thumbs.db
   *.tmp
   desktop.ini
   .sync*
   ```

7. **Advanced Tab**:
   - **Watch for Changes**: Enable (detect playlist exports immediately)
   - **Scan Interval**: 60 seconds

8. Click "Save"

### On Windows (Accept Playlists Folder)

1. Windows shows notification: "Linux-Laptop wants to share folder 'Music Minion Playlists'"

2. Click "Add"

3. **Configure Folder Path**:
   - **Folder Path**: Location where Serato reads playlists
   - **Common locations**:
     - `C:\Users\YourName\Music\_Serato_\Playlists`
     - `C:\Users\YourName\Music\Playlists`
   - **Important**: Use Serato's playlist location for direct integration

4. **Folder Type**: "Send & Receive" (bidirectional)

5. **File Versioning**: Enable (Simple, keep 3 versions)

6. Click "Save"

### Configure Serato to Read Synced Playlists

**Option 1: Sync to Serato's Playlist Folder**
- Set Windows path to: `C:\Users\YourName\Music\_Serato_\Playlists`
- Serato automatically detects .crate files
- No additional configuration needed

**Option 2: Import Playlists Manually**
- Sync to: `C:\Users\YourName\Music\Playlists`
- In Serato: File → Import Playlist → Browse to synced .crate files
- Must re-import after changes

**Recommended**: Option 1 (automatic detection)

### Verify Playlist Sync

1. **On Linux** (create test playlist):
   ```bash
   music-minion
   > playlist new manual "Test Sync"
   > add "Test Sync"  # Add current track
   > playlist export "Test Sync" crate
   ```

2. **Check Syncthing**:
   - Linux: Verify .crate file appears in export_path
   - Syncthing: Shows sync progress
   - Windows: File appears in configured location

3. **Check Serato** (Windows):
   - Open Serato DJ Pro
   - Playlists panel should show "Test Sync"
   - Click to view tracks

4. **Test Bidirectional Sync**:
   - Windows: Add track to playlist in Serato
   - Syncthing: Syncs .crate back to Linux
   - Linux: Restart Music Minion
   - Verify: `playlist show "Test Sync"` includes added track

### Auto-Export Configuration

Enable automatic playlist export in Music Minion config:

```toml
[playlists]
auto_export = true                  # Export on playlist changes
export_formats = ["m3u8", "crate"]  # Both formats
export_path = "/home/yourusername/Music/Playlists"
use_relative_paths = true           # Portable across machines
```

**With auto-export enabled**:
1. Create/modify playlist in Music Minion
2. Playlist automatically exports
3. Syncthing syncs to Windows
4. Serato sees updated playlist

---

## Music Minion Integration

### Verify Auto-Sync Settings

Check Music Minion config: `~/.config/music-minion/config.toml`

```toml
[sync]
auto_export_on_change = true    # Export tags to files immediately
auto_import_on_startup = true   # Import changes from files on startup
use_comment_field = true        # Store tags in COMMENT field
tag_prefix = "mm:"              # Prefix for Music Minion tags
```

### Workflow Verification

1. **Linux → Windows**:
   ```bash
   # In Music Minion, add tag to current track
   tag energetic

   # Auto-export writes to file
   # Syncthing syncs file to Windows
   # Check Windows: file has tag in metadata
   ```

2. **Windows → Linux**:
   - Edit tags in Serato (or any Windows tag editor)
   - Syncthing syncs changes back to Linux
   - Restart Music Minion (or wait for startup)
   - Changes imported automatically
   - Verify: `sync status` shows imported changes

---

## Optimization & Best Practices

### Performance Optimization

**Linux**:
```bash
# Increase inotify watches if you have large library
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**Both Machines**:
- Settings → Connections → Rate Limits
- Leave unlimited for LAN sync
- Set limits if syncing over internet

### Network Configuration

**LAN Sync** (fastest):
- Default settings work automatically
- Devices discover each other via local network
- No configuration needed

**Internet Sync** (if not on same network):
- Settings → Connections
- Enable "Enable Relaying" (uses Syncthing relay servers)
- Or configure port forwarding for direct connection

### Ignore Patterns for Music Libraries

Add to ignore patterns to exclude non-music files:

```
# OS files
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.part
*.crdownload
*.!ut

# System folders
.sync*
.stfolder
.stversions

# Music Minion database (DO NOT SYNC - local only)
.music-minion.db

# IMPORTANT: DO NOT ignore these files:
# *.mp3, *.m4a    - Your music files
# *.crate         - Serato playlist files (MUST sync)
# *.m3u8          - M3U8 playlist files (MUST sync)
# _Serato_/*      - Serato folder (if you want cue points/beatgrids)
```

**Note for Playlists Folder**: The ignore patterns above work for the Music Library folder. For the dedicated Playlists folder, you typically don't need any ignore patterns since you want to sync all .crate and .m3u8 files.

### File Versioning Strategy

**Recommended Settings**:
- **Type**: Simple File Versioning
- **Keep Versions**: 5-10
- **Clean out after**: 30-90 days

**Why**: Protects against:
- Accidental tag removal
- File corruption
- Sync conflicts
- Metadata overwrites

### Bandwidth Management

**For Large Libraries**:
1. Initial sync over LAN (much faster)
2. Settings → Bandwidth:
   - Upload Rate: Unlimited (LAN)
   - Download Rate: Unlimited (LAN)
3. Only limit if syncing over mobile hotspot

---

## Troubleshooting

### Devices Not Connecting

**Check 1: Firewall**

Linux:
```bash
# Allow Syncthing ports
sudo ufw allow 22000/tcp  # Sync protocol
sudo ufw allow 21027/udp  # Discovery
```

Windows:
- Windows Defender → Allow Syncthing through firewall
- Should be automatic during installation

**Check 2: Network Discovery**

- Both devices on same network?
- Settings → Connections → "Local Discovery" enabled?
- If different networks, enable "Global Discovery" and "Relaying"

**Check 3: Device IDs**

- Verify Device IDs copied correctly
- Device ID is case-sensitive

### Sync Conflicts

**Symptom**: Files with `.sync-conflict-*` suffix

**Cause**: Both machines modified same file simultaneously

**Resolution**:
1. Open both versions
2. Decide which to keep (or merge manually)
3. Delete/rename conflict file
4. Music Minion: `sync import` to update database

**Prevention**:
- Edit on one machine at a time
- Let Syncthing finish before editing on other machine

### Files Not Syncing

**Check 1: Folder State**
- Web UI → Folder status
- Look for errors or warnings

**Check 2: Ignore Patterns**
- Settings → Edit Folder → Ignore Patterns
- Verify not accidentally excluding files

**Check 3: Permissions**
```bash
# Linux - verify permissions
ls -la ~/Music

# Syncthing user should have read/write access
```

**Check 4: Disk Space**
- Verify sufficient space on destination

### High CPU Usage

**Cause**: Large library with many changes

**Solutions**:
1. Increase scan interval:
   - Edit Folder → Advanced → Scan Interval: 300 seconds
2. Disable watch for changes temporarily
3. Reduce file versioning (fewer versions to track)

### Out of Sync

**Force Rescan**:
- Web UI → Folder → Actions → "Rescan"
- Forces Syncthing to check all files

**Override Changes** (use carefully):
- Edit Folder → Advanced → "Folder Type"
- Temporarily set to "Send Only" on authoritative machine
- Sync, then change back to "Send & Receive"

---

## Security Considerations

### Local Network Only (Recommended)

For Linux + Windows on same home network:
- Default settings are secure
- Traffic stays on local network
- No internet exposure

### Internet Sync (Advanced)

If syncing over internet:

1. **Use Relay Servers** (easier):
   - Settings → Connections → Enable "Enable Relaying"
   - Traffic encrypted, routed through Syncthing relays
   - Slower than direct connection

2. **Direct Connection** (faster, requires setup):
   - Configure port forwarding on router
   - Forward port 22000 TCP to machine
   - More complex, requires network knowledge

3. **Security Best Practices**:
   - Always use GUI password (Settings → GUI)
   - Keep Syncthing updated (security patches)
   - Use strong device IDs (default is secure)

### Data Privacy

- **All sync traffic is encrypted** (TLS)
- Only devices you authorize can connect
- No cloud storage (peer-to-peer only)
- Relay servers cannot read your data

---

## Monitoring & Maintenance

### Check Sync Status

**Web UI**:
- Folder shows "Up to Date" when synced
- Device shows "Connected" when online
- Global State shows total files/data

**Command Line** (Linux):
```bash
# Check service status
systemctl --user status syncthing

# View logs
journalctl --user -u syncthing -f
```

### View Sync Statistics

Web UI → Folder → Click folder name:
- Total items: File count
- Global state: Total size
- Local state: Size on this device
- Out of sync: Pending changes

### Regular Maintenance

**Monthly Tasks**:
1. Check for Syncthing updates
2. Review sync conflicts (if any)
3. Clean up versioned files (if space limited)
4. Verify Music Minion sync with `sync status`

**Update Syncthing**:

Linux:
```bash
# Package manager will update
sudo pacman -Syu syncthing  # Arch
sudo apt update && sudo apt upgrade syncthing  # Ubuntu
```

Windows:
- Syncthing auto-updates by default
- Or download latest installer and reinstall

---

## Advanced: Multiple Machines

If you have more than 2 machines (e.g., Linux desktop, Linux laptop, Windows DJ):

### Star Topology (Recommended)

One machine as "hub", others connect to it:
```
Linux Desktop (Hub)
    ├── Windows DJ
    └── Linux Laptop
```

**Benefits**:
- Simpler configuration
- Fewer connections to manage
- Hub can be always-on server

### Mesh Topology

All machines connect to all others:
```
    Linux Desktop
        ⇅
Windows DJ ⇄ Linux Laptop
```

**Benefits**:
- Faster sync (direct paths)
- No single point of failure

**Setup**: Add each device to all others, share folder with all

---

## Music Minion + Syncthing Workflow

### Complete Workflow Example

**Friday Night - Curation Session on Linux**:
1. Start Music Minion: `music-minion`
2. Play tracks, add tags: `tag energetic`, `tag heavy-bass`
3. Create playlist: `playlist new manual "NYE 2025 Set"`
4. Add tracks: `add "NYE 2025 Set"`
5. Tags auto-export to file metadata
6. Playlist auto-exports to .crate format
7. Syncthing syncs files and playlists to Windows (background)
8. Exit Music Minion

**Saturday Night - DJ Set on Windows**:
1. Open Serato DJ Pro
2. "NYE 2025 Set" playlist appears in Serato
3. View tags in Serato track info
4. Reorder tracks, add cue points in Serato
5. Changes saved to .crate file
6. Syncthing syncs changes back to Linux (background)

**Sunday Morning - Review on Linux**:
1. Start Music Minion: `music-minion`
2. Auto-import loads changes from files
3. Playlist import updates track order
4. View updated playlist: `playlist show "NYE 2025 Set"`
5. Continue curating and refining

### Conflict Prevention

**Best Practice**: Work on one machine at a time
- **Don't**: Edit same track simultaneously on both machines
- **Do**: Let Syncthing finish syncing before switching machines
- **Check**: Web UI shows "Up to Date" before switching

### Backup Strategy

**Syncthing is NOT a backup solution** - it syncs changes (including deletions)

**Recommended Backup**:
1. **File-level**: Separate backup tool (rsync, Timeshift, Backblaze)
2. **Database**: Music Minion database (`~/.local/share/music-minion/music_minion.db`)
3. **Versioning**: Enable file versioning in Syncthing (keeps recent versions)

---

## Quick Reference

### Common Commands

**Linux**:
```bash
# Start Syncthing
systemctl --user start syncthing

# Stop Syncthing
systemctl --user stop syncthing

# Restart Syncthing
systemctl --user restart syncthing

# View status
systemctl --user status syncthing

# View logs
journalctl --user -u syncthing -f
```

**Access Web UI**:
- Linux: http://localhost:8384
- Windows: http://localhost:8384
- Or click system tray icon

### Key Settings Locations

**Linux**:
- Config: `~/.config/syncthing/`
- Database: `~/.config/syncthing/index-*.db`
- Synced folders:
  - Music Library: `~/Music` (or your library path)
  - Playlists: `~/Music/Playlists` (or your export_path)

**Windows**:
- Config: `C:\Users\YourName\AppData\Local\Syncthing\`
- Synced folders:
  - Music Library: `C:\Users\YourName\Music` (or your library path)
  - Playlists: `C:\Users\YourName\Music\_Serato_\Playlists` (or custom path)

### Important Settings

| Setting | Location | Recommended Value |
|---------|----------|-------------------|
| Folder Type | Edit Folder → General | Send & Receive |
| File Versioning | Edit Folder → File Versioning | Simple (5-10 versions) |
| Watch for Changes | Edit Folder → Advanced | Enabled |
| Scan Interval | Edit Folder → Advanced | 60 seconds |
| GUI Password | Settings → GUI | Set password for security |

---

## Support & Resources

### Official Documentation
- Website: https://syncthing.net/
- Docs: https://docs.syncthing.net/
- Forum: https://forum.syncthing.net/

### Music Minion Sync Documentation
- See `docs/playlist-system-plan.md` Phase 7
- See `ai-learnings.md` section "Critical Learnings from Phase 7 Code Review"

### Getting Help

**Syncthing Issues**:
- Check Web UI for error messages
- View logs: `journalctl --user -u syncthing -f` (Linux)
- Forum: https://forum.syncthing.net/

**Music Minion Sync Issues**:
- Check: `sync status` in Music Minion
- Verify: File metadata with `sync export`, `sync import`
- Debug: Enable verbose logging in config.toml

---

**Last Updated**: 2025-09-29
**Tested With**: Syncthing v1.27+, Music Minion Phase 7
**Primary Use Case**: Linux (Music Minion) ↔ Windows (Serato) music library sync