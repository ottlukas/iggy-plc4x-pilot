# Troubleshooting Guide - IoTDB + Superset Integration

This guide provides solutions to common issues encountered when running the iggy-plc4x-pilot project.

## Table of Contents

1. [General Issues](#general-issues)
2. [Docker Issues](#docker-issues)
3. [IoTDB Issues](#iotdb-issues)
4. [Superset Issues](#superset-issues)
5. [HMI Issues](#hmi-issues)
6. [Pipeline Issues](#pipeline-issues)
7. [Performance Issues](#performance-issues)
8. [Platform-Specific Issues](#platform-specific-issues)

---

## General Issues

### Services fail to start

**Symptoms**: Containers crash immediately or fail to start.

**Check**:
```bash
# View container logs
docker compose logs <service_name>

# Check container status
docker compose ps

# View detailed error
docker compose ps -a
```

**Common Causes**:
- Port conflicts (port already in use)
- Insufficient memory
- Missing dependencies
- Invalid configuration

**Solutions**:
1. **Port conflicts**: Change the port mapping in `docker-compose.yml` or stop the conflicting service.
2. **Insufficient memory**: Increase Docker memory allocation (minimum 4GB recommended).
3. **Missing dependencies**: Ensure Docker and Docker Compose are installed correctly.
4. **Invalid configuration**: Validate with `docker compose config --quiet`.

---

### Container starts but service is unhealthy

**Symptoms**: Container is running but service is not responding.

**Check**:
```bash
# Check service health via HMI
# Open http://localhost:8080 and check service status

# Or check manually
docker exec <container_name> curl -f http://localhost:<port>/health || echo "Unhealthy"
```

**Common Causes**:
- Service not fully initialized
- Network connectivity issues
- Authentication failures

**Solutions**:
1. Wait longer for service initialization (Superset can take 20-30 seconds)
2. Check network connectivity between containers: `docker network inspect iggy-plc4x-pilot_default`
3. Verify credentials in `config.toml`

---

## Docker Issues

### Docker Compose configuration error

**Symptoms**: `docker compose config` fails with errors.

**Check**:
```bash
docker compose config
```

**Common Causes**:
- Invalid YAML syntax
- Missing required fields
- Invalid image names

**Solutions**:
1. Validate YAML syntax using a YAML validator
2. Check all required fields are present
3. Ensure image names are correct and accessible

---

### Docker socket permission denied (Linux)

**Symptoms**: HMI container fails with permission denied on Docker socket.

**Error**:
```
ERROR: for hmi  Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**Solutions**:
1. Add user to Docker group:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```
2. Restart Docker daemon:
   ```bash
   sudo systemctl restart docker
   ```
3. Ensure Docker socket has correct permissions:
   ```bash
   sudo chmod 666 /var/run/docker.sock
   ```

---

### Docker Desktop not running (macOS/Windows)

**Symptoms**: Docker commands fail with "Docker daemon not running".

**Solutions**:
1. Start Docker Desktop application
2. Wait for Docker to fully initialize (check status in menu bar/system tray)
3. Restart terminal session

---

### Image pull fails

**Symptoms**: Docker fails to pull images from Docker Hub.

**Error**:
```
ERROR: for bifromq  pull access denied for apache/bifromq, repository does not exist or may require 'docker login'
```

**Solutions**:
1. Check internet connectivity
2. Try pulling manually: `docker pull apache/bifromq:4.0.0-incubating`
3. Check Docker Hub rate limits (anonymous users have limits)
4. Log in to Docker Hub: `docker login`

---

### Build fails due to cache issues

**Symptoms**: Build fails with cache-related errors.

**Solutions**:
1. Clean Docker build cache:
   ```bash
   docker builder prune
   ```
2. Rebuild with no cache:
   ```bash
   docker compose build --no-cache
   ```
3. Remove old containers and volumes:
   ```bash
   docker compose down -v
   docker compose up --build -d
   ```

---

## IoTDB Issues

### IoTDB REST API not responding

**Symptoms**: IoTDB REST API returns connection refused or timeout.

**Check**:
```bash
# Check if IoTDB container is running
docker compose ps | grep iotdb

# Check IoTDB logs
docker compose logs iotdb

# Test REST API directly
curl -u root:root http://localhost:18080/rest/v2/settings
```

**Common Causes**:
- IoTDB not fully initialized
- REST service not enabled
- Port not exposed

**Solutions**:
1. Wait for IoTDB to fully initialize (can take 10-15 seconds)
2. Verify REST service is enabled in `docker-compose.yml`:
   ```yaml
   environment:
     enable_rest_service: "true"
   ```
3. Check port mapping: `18080:18080`

---

### IoTDB query returns no data

**Symptoms**: Query returns empty results or no rows.

**Check**:
```bash
# Query IoTDB directly
curl -u root:root -X POST http://localhost:18080/rest/v2/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT temperature FROM root.sg.line_1"}'

# Check if data exists
curl -u root:root -X POST http://localhost:18080/rest/v2/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SHOW DEVICES"}'
```

**Common Causes**:
- Pipeline not running
- No data written yet
- Wrong device path
- Time range too narrow

**Solutions**:
1. Check pipeline is running via HMI or `docker compose ps`
2. Wait for first data to be written (can take 1-2 seconds after pipeline starts)
3. Verify device path in `config.toml`:
   ```toml
   [iotdb]
   device_prefix = "root.sg"
   ```
4. Try broader time range:
   ```sql
   SELECT temperature FROM root.sg.line_1 WHERE time >= 0
   ```

---

### IoTDB connection refused

**Symptoms**: Connection refused when trying to connect to IoTDB.

**Check**:
```bash
# Test TCP connection
telnet localhost 6667
telnet localhost 18080

# Check if IoTDB is listening
netstat -tuln | grep 6667
netstat -tuln | grep 18080
```

**Solutions**:
1. Verify IoTDB container is running
2. Check port mappings in `docker-compose.yml`
3. Restart IoTDB container:
   ```bash
   docker compose restart iotdb
   ```

---

## Superset Issues

### Superset not accessible

**Symptoms**: Cannot access Superset at `http://localhost:8088`.

**Check**:
```bash
# Check if Superset container is running
docker compose ps | grep superset

# Check Superset logs
docker compose logs superset

# Test Superset health
curl http://localhost:8088/health
```

**Common Causes**:
- Superset not fully initialized
- Port conflict
- Database migration failed

**Solutions**:
1. Wait for Superset to initialize (can take 20-30 seconds)
2. Check for port conflicts: `lsof -i :8088` or `netstat -tuln | grep 8088`
3. View initialization logs:
   ```bash
   docker compose logs superset
   ```
4. Restart Superset:
   ```bash
   docker compose restart superset
   ```

---

### Superset login fails

**Symptoms**: Cannot login to Superset with default credentials.

**Check**:
- Default credentials: `admin` / `admin`
- Check if admin user was created (look for "admin already exists" in logs)

**Solutions**:
1. Verify environment variables in `docker-compose.yml`:
   ```yaml
   environment:
     SUPERSET_ADMIN_USERNAME: admin
     SUPERSET_ADMIN_PASSWORD: admin
     SUPERSET_ADMIN_EMAIL: admin@example.com
   ```
2. Restart Superset to recreate admin user:
   ```bash
   docker compose down -v
   docker compose up --build -d
   ```
3. Check Superset logs for admin creation:
   ```bash
   docker compose logs superset | grep "admin"
   ```

---

### Superset cannot connect to IoTDB

**Symptoms**: Superset shows connection error when testing IoTDB database.

**Check**:
```bash
# Test IoTDB connection from Superset container
docker compose exec superset curl -u root:root http://iotdb:18080/rest/v2/settings
```

**Common Causes**:
- Wrong connection URI
- IoTDB not running
- Network connectivity issues
- SQLAlchemy dialect incompatibility

**Solutions**:
1. Verify connection URI: `iotdb://root:root@iotdb:6667` (use service name, not localhost)
2. Check IoTDB is running: `docker compose ps | grep iotdb`
3. Test network connectivity:
   ```bash
   docker compose exec superset ping iotdb
   docker compose exec superset nc -zv iotdb 6667
   ```
4. Use the correct SQLAlchemy dialect version (apache-iotdb==2.0.11)

---

### Superset SQL Lab query fails

**Symptoms**: Query in SQL Lab returns error or no results.

**Check**:
```bash
# Check Superset logs for query errors
docker compose logs superset

# Test query directly against IoTDB
curl -u root:root -X POST http://localhost:18080/rest/v2/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT temperature FROM root.sg.line_1"}'
```

**Common Causes**:
- Wrong database selected
- Invalid SQL syntax for IoTDB
- No data in database
- Time range too narrow

**Solutions**:
1. Select the IoTDB database in SQL Lab
2. Use IoTDB SQL syntax (not standard SQL):
   ```sql
   SELECT temperature FROM root.sg.line_1
   ```
3. Check if data exists:
   ```sql
   SELECT COUNT(temperature) FROM root.sg.line_1
   ```
4. Try broader time range:
   ```sql
   SELECT temperature FROM root.sg.line_1 WHERE time >= 0
   ```

---

### Dashboard not visible

**Symptoms**: Dashboard is not shown in Superset after initialization.

**Check**:
```bash
# Check if dashboard was created
docker compose exec superset superset list-dashboards

# Check initialization logs
docker compose logs superset | grep "dashboard"
```

**Solutions**:
1. Wait for initialization to complete (can take 10-15 seconds after Superset starts)
2. Manually import dashboard:
   - Go to **Dashboards** > **+ Dashboard** > **Import JSON**
   - Upload `superset/dashboards/plc_iot_dashboard.json`
3. Check initialization script ran:
   ```bash
   docker compose exec superset ps aux | grep init_superset
   ```

---

## HMI Issues

### HMI not accessible

**Symptoms**: Cannot access HMI at `http://localhost:8080`.

**Check**:
```bash
# Check if HMI container is running
docker compose ps | grep hmi

# Check HMI logs
docker compose logs hmi

# Test HMI health
curl http://localhost:8080/api/health
```

**Common Causes**:
- HMI not fully initialized
- Port conflict
- Docker socket not mounted

**Solutions**:
1. Wait for HMI to initialize (usually < 5 seconds)
2. Check for port conflicts: `lsof -i :8080` or `netstat -tuln | grep 8080`
3. Verify Docker socket is mounted:
   ```bash
   docker inspect iggy-plc4x-pilot-hmi-1 | grep docker.sock
   ```
4. Restart HMI:
   ```bash
   docker compose restart hmi
   ```

---

### HMI shows services as down

**Symptoms**: HMI shows red status for services that are running.

**Check**:
```bash
# Check HMI API for service status
curl http://localhost:8080/api/pipeline/status

# Check individual service
curl http://localhost:8080/api/services/iotdb
```

**Common Causes**:
- Health check probes failing
- Network connectivity issues
- Service not fully initialized

**Solutions**:
1. Check service logs:
   ```bash
   docker compose logs iotdb
   ```
2. Test health check manually:
   ```bash
   # For IoTDB
   curl -u root:root http://iotdb:18080/rest/v2/settings
   
   # For Superset
   curl http://superset:8088/health
   ```
3. Wait for services to fully initialize
4. Check HMI configuration in `hmi/main.py` for probe logic

---

### HMI START/STOP buttons not working

**Symptoms**: Clicking START or STOP buttons has no effect.

**Check**:
```bash
# Check HMI logs for errors
docker compose logs hmi

# Test API manually
curl -X POST http://localhost:8080/api/pipeline/start
curl -X POST http://localhost:8080/api/pipeline/stop
```

**Common Causes**:
- Docker socket not accessible
- Compose project name mismatch
- Insufficient permissions

**Solutions**:
1. Verify Docker socket is mounted:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock:ro
   ```
2. Check COMPOSE_PROJECT_NAME environment variable:
   ```yaml
   environment:
     COMPOSE_PROJECT_NAME: iggy-plc4x-pilot
   ```
3. Verify Docker permissions (Linux):
   ```bash
   ls -la /var/run/docker.sock
   ```
4. Restart HMI with correct permissions:
   ```bash
   docker compose down
   docker compose up --build -d
   ```

---

## Pipeline Issues

### No data flowing through pipeline

**Symptoms**: HMI shows pipeline running but no data in IoTDB.

**Check**:
```bash
# Check each component
curl http://localhost:8080/api/services/modbus-simulator
curl http://localhost:8080/api/services/plc4x-bridge
curl http://localhost:8080/api/services/mqtt-to-iggy
curl http://localhost:8080/api/services/iggy-to-iotdb

# Check MQTT messages
docker compose exec bifromq mosquitto_sub -t "iggy/plc/#" -v

# Check Iggy stream
docker compose exec iggy iggy-cli consumer info --stream plc_raw --consumer-group test
```

**Common Causes**:
- One or more pipeline services not running
- Configuration mismatch
- Network connectivity issues

**Solutions**:
1. Check all pipeline services are running:
   ```bash
   docker compose ps | grep -E "(modbus-simulator|plc4x-bridge|mqtt-to-iggy|iggy-to-iotdb)"
   ```
2. Verify configuration in `config.toml`:
   ```toml
   [plc]
   endpoint = "modbus-tcp://modbus-simulator:502"
   
   [mqtt]
   host = "bifromq"
   port = 1883
   
   [iggy]
   address = "iggy:8090"
   
   [iotdb]
   endpoint = "http://iotdb:18080/rest/v2/nonQuery"
   ```
3. Check logs for each service:
   ```bash
   docker compose logs modbus-simulator
   docker compose logs plc4x-bridge
   docker compose logs mqtt-to-iggy
   docker compose logs iggy-to-iotdb
   ```
4. Restart pipeline:
   ```bash
   docker compose restart modbus-simulator plc4x-bridge mqtt-to-iggy iggy-to-iotdb
   ```

---

### Data flowing but wrong values

**Symptoms**: Temperature values are not incrementing or are incorrect.

**Check**:
```bash
# Query IoTDB for recent values
curl -u root:root -X POST http://localhost:18080/rest/v2/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT temperature FROM root.sg.line_1 ORDER BY time DESC LIMIT 10"}'
```

**Common Causes**:
- Simulator not working correctly
- PLC4X reading wrong register
- Data transformation error

**Solutions**:
1. Check simulator is incrementing register:
   ```bash
   docker compose logs modbus-simulator
   ```
2. Verify PLC4X configuration:
   ```toml
   [[plc.tags]]
   name = "temperature"
   address = "holding-register:1:UINT"
   ```
   Note: PLC4X uses 1-based addressing, so `holding-register:1` reads wire register 0.
3. Check MQTT messages:
   ```bash
   docker compose exec bifromq mosquitto_sub -t "iggy/plc/line_1/temperature" -v
   ```

---

## Performance Issues

### Slow startup

**Symptoms**: Services take a long time to start.

**Solutions**:
1. First run builds images (5-10 minutes), subsequent runs are faster
2. Use cached images:
   ```bash
   docker compose up -d  # Without --build if images already exist
   ```
3. Pre-pull images:
   ```bash
   docker pull apache/bifromq:4.0.0-incubating
   docker pull apache/iggy:edge
   docker pull apache/iotdb:2.0.5-standalone
   docker pull apache/superset:4.1.1
   ```

---

### High memory usage

**Symptoms**: System runs out of memory.

**Solutions**:
1. Increase Docker memory allocation (minimum 4GB recommended)
2. Limit Iggy memory:
   ```yaml
   iggy:
     mem_limit: 2g
   ```
3. Reduce number of running services during development
4. Use Docker prune to clean up:
   ```bash
   docker system prune -a
   ```

---

## Platform-Specific Issues

### Linux

#### Permission denied on Docker socket
See [Docker socket permission denied](#docker-socket-permission-denied-linux) above.

#### SELinux blocking access
**Symptoms**: Containers fail with permission denied on mounted volumes.

**Solutions**:
1. Temporarily disable SELinux:
   ```bash
   sudo setenforce 0
   ```
2. Or add SELinux context:
   ```yaml
   volumes:
     - ./config.toml:/app/config.toml:ro,z
   ```

---

### macOS

#### Docker Desktop not starting
**Symptoms**: Docker Desktop fails to start.

**Solutions**:
1. Restart Docker Desktop
2. Check for updates
3. Restart computer
4. Check Docker Desktop logs: `/Users/<user>/Library/Containers/com.docker.docker/Data/vms/0/.../logs`

---

#### File sharing not working
**Symptoms**: Mounted volumes not accessible in containers.

**Solutions**:
1. Check file sharing in Docker Desktop settings
2. Add project directory to file sharing list
3. Restart Docker Desktop

---

### Windows

#### Docker Desktop not starting
See macOS solution above.

---

#### Line endings causing issues
**Symptoms**: Shell scripts fail with line ending errors.

**Solutions**:
1. Convert line endings to LF:
   ```bash
   # In Git Bash or WSL
   dos2unix start-superset.sh
   dos2unix hmi/main.py
   ```
2. Or configure Git to handle line endings:
   ```bash
   git config --global core.autocrlf input
   ```

---

#### Docker socket path different
**Symptoms**: Docker socket not found at `/var/run/docker.sock`.

**Solutions**:
1. Use the correct path for Windows:
   ```yaml
   volumes:
     - //var/run/docker.sock:/var/run/docker.sock:ro
   ```
2. Or use Docker Desktop's named pipe:
   ```yaml
   volumes:
     - \\\\.\pipe\docker_engine:\\\\.\pipe\docker_engine:ro
   ```

---

## Debugging Tools

### View all container logs
```bash
docker compose logs -f
```

### View specific container logs
```bash
docker compose logs -f <service_name>
```

### Enter container shell
```bash
docker compose exec <service_name> sh
# or for Python containers
docker compose exec <service_name> bash
```

### Check container resource usage
```bash
docker stats
```

### Check network connectivity
```bash
# From host to container
docker compose exec <service_name> ping <other_service>

# Check DNS resolution
docker compose exec <service_name> nslookup <other_service>

# Test TCP connection
docker compose exec <service_name> nc -zv <other_service> <port>
```

### Check mounted volumes
```bash
docker inspect <container_name> | grep -A 10 Mounts
```

---

## Getting Help

### Collect diagnostic information

When reporting issues, please include:

1. **Environment**:
   - Operating system and version
   - Docker version: `docker --version`
   - Docker Compose version: `docker compose version`
   - Architecture: `uname -m`

2. **Configuration**:
   - `docker-compose.yml` (if modified)
   - `config.toml` (if modified)

3. **Logs**:
   - Full logs from failing service: `docker compose logs <service_name>`
   - HMI status: `curl http://localhost:8080/api/pipeline/status`

4. **Steps to reproduce**:
   - What you did
   - What you expected to happen
   - What actually happened

### Common commands for diagnostics

```bash
# Check all services
docker compose ps -a

# Check resource usage
docker stats --no-stream

# Check disk usage
docker system df

# Check network
docker network inspect iggy-plc4x-pilot_default

# Check volumes
docker volume ls
```

---

## Reset Everything

If all else fails, you can reset the entire environment:

```bash
# Stop and remove all containers, networks, and volumes
docker compose down -v --remove-orphans

# Remove all Docker resources (CAUTION: removes ALL Docker data)
docker system prune -a --volumes

# Rebuild and start from scratch
docker compose up --build -d
```

---

**Last Updated**: 2026-10-16
**Repository**: ottlukas/iggy-plc4x-pilot
**Branch**: main
