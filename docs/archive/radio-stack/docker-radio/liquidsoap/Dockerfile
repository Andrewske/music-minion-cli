FROM savonet/liquidsoap:v2.2.5

# ffmpeg is already included in the base image
# Liquidsoap has built-in HTTP functions (http.get)

# Copy the Liquidsoap script
COPY radio.liq /etc/liquidsoap/radio.liq

# Expose telnet control port
EXPOSE 1234

# Run Liquidsoap with the radio script
CMD ["liquidsoap", "/etc/liquidsoap/radio.liq"]
