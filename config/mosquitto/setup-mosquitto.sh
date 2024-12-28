#!/bin/sh

# Create password file
touch /mosquitto/config/passwd

# Add user with password
mosquitto_passwd -b /mosquitto/config/passwd maia maia

# Set permissions
chmod 644 /mosquitto/config/passwd 