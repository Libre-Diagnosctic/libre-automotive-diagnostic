/**
 * @file web_server.c
 * @brief Embedded HTTP/1.1 Web Console & Diagnostic REST API Router
 * @details Realizes light-weight vehicle diagnostics gateway pooling over Wi-Fi/Ethernet.
 *          Strictly utilizes memory-safe buffer routines to prevent boundary overruns.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <pthread.h>
#include "../../driver/obd_ioctl.h"
#include "../../lib/config_loader.h"
#include "../../lib/uds_did_db.h"
#include "../../lib/websocket_server.h"
#include "../../lib/iso_tp_stack.h"
#include "../../lib/uds_iso14229.h"
#include "../core/security_unlock.h"
#include "../core/variant_coding.h"
#include "../core/immo_keygen.h"
#include "json_formatter.h"

#define WEB_SERVER_PORT_DEFAULT 80U
#define WEB_CONFIG_PATH_DEFAULT "/etc/kobd/obd.conf"
#define MAX_HTTP_REQUEST        2048U
#define JSON_BUF_SIZE           4096U
#define WS_PUSH_INTERVAL_US     200000U   /* 5 Hz live telemetry push */
#define DIAG_CHANNEL_TX_ID      0x7E0U
#define DIAG_CHANNEL_RX_ID      0x7E8U

/**
 * @brief Extracts a numeric query parameter from an HTTP GET line
 */
static int32_t http_query_get_int(const char *request, const char *key, int32_t defval) {
    char needle[48];
    (void)snprintf(needle, sizeof(needle), "%s=", key);

    const char *p = strstr(request, needle);
    if (p == NULL) {
        return defval;
    }
    p += strlen(needle);

    char val[24];
    uint32_t i = 0U;
    while ((i < (uint32_t)(sizeof(val) - 1U)) && (*p != '\0') && (*p != '&') &&
           (*p != '\r') && (*p != '\n') && (*p != ' ')) {
        val[i++] = *p++;
    }
    val[i] = '\0';
    if (val[0] == '\0') {
        return defval;
    }
    return (int32_t)strtol(val, NULL, 0);
}

/**
 * @brief Executes a diagnostic service operation on a temporary ISO-TP channel
 * @return HTTP status code (200 OK, 403 forbidden, 500 error)
 */
static int vci_diag_api(const char *request, char *out, size_t out_len) {
    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, WEB_CONFIG_PATH_DEFAULT);

    /* Default-deny: diagnostic write access must be explicitly enabled */
    if (!config_get_bool(&config, "diag", "web_access", false)) {
        (void)snprintf(out, out_len, "{\"result\":\"forbidden\"}");
        return 403;
    }

    const char *iface = config_get_string(&config, "can", "interface", "can0");

    int fd = isotp_stack_init(iface, DIAG_CHANNEL_TX_ID, DIAG_CHANNEL_RX_ID);
    if (fd < 0) {
        (void)snprintf(out, out_len, "{\"result\":\"error\",\"code\":-100}");
        return 500;
    }

    int rc;
    if (strstr(request, "/api/diag/security") != NULL) {
        int32_t level = http_query_get_int(request, "level", 1);
        rc = vci_security_unlock(fd, (uint8_t)level);
    } else if (strstr(request, "/api/diag/variant") != NULL) {
        int32_t did = http_query_get_int(request, "did", 0xF100);
        int32_t off = http_query_get_int(request, "offset", 0);
        int32_t mask = http_query_get_int(request, "mask", 0xFF);
        int32_t val = http_query_get_int(request, "value", 0);
        rc = vci_execute_variant_coding(fd, (uint16_t)did, (uint16_t)off,
                                        (uint8_t)mask, (uint8_t)val);
    } else if (strstr(request, "/api/diag/adapt") != NULL) {
        int32_t did = http_query_get_int(request, "did", 0);
        int32_t val = http_query_get_int(request, "value", 0);
        int32_t sz = http_query_get_int(request, "size", 1);
        rc = vci_execute_adaptation(fd, (uint16_t)did, (uint32_t)val, (uint8_t)sz);
    } else if (strstr(request, "/api/diag/immo") != NULL) {
        const char *op = "count";
        if (strstr(request, "op=count") != NULL) {
            int32_t kc = vci_immo_get_key_count(fd);
            (void)snprintf(out, out_len, "{\"result\":\"ok\",\"key_count\":%d}", (int)kc);
            isotp_stack_close(fd);
            return 200;
        } else if (strstr(request, "op=auth") != NULL) {
            int32_t table = http_query_get_int(request, "table", 0);
            rc = vci_immo_authenticate(fd, (uint8_t)table);
        } else if (strstr(request, "op=learn") != NULL) {
            rc = vci_immo_enter_learning_mode(fd);
        } else {
            rc = -200;
        }
    } else if (strstr(request, "/api/diag/reset") != NULL) {
        int32_t type = http_query_get_int(request, "type", 1);
        rc = uds_ecu_reset(fd, (uint8_t)type);
    } else if (strstr(request, "/api/diag/cleardtc") != NULL) {
        rc = uds_clear_dtc(fd, 0xFFFFFFU);
    } else if (strstr(request, "/api/diag/session") != NULL) {
        int32_t type = http_query_get_int(request, "type", 3);
        rc = uds_set_session(fd, (uint8_t)type);
    } else {
        rc = -404;
    }

    isotp_stack_close(fd);
    (void)snprintf(out, out_len, "{\"result\":\"%s\",\"code\":%d}",
                   (rc == 0) ? "ok" : "error", rc);
    return 200;
}

/**
 * @brief Dispatches a formatted HTTP/1.1 response container carrying raw JSON data payload
 */
static void send_json_response(int32_t client_socket, const char *json_data) {
    if ((client_socket < 0) || (json_data == NULL)) {
        return;
    }

    char header[256U];
    size_t len = strlen(json_data);

    /* Secure bounded string formatting tracking layout allocation bounds */
    int32_t written = snprintf(header, sizeof(header), 
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: %u\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Connection: close\r\n\r\n", (unsigned int)len);

    if ((written > 0) && ((size_t)written < sizeof(header))) {
        (void)send(client_socket, header, strlen(header), 0);
        (void)send(client_socket, json_data, len, 0);
    }
}

/**
 * @brief WebSocket live telemetry streaming session (RFC 6455)
 */
static void web_handle_websocket(int32_t client_socket, const char *request,
                                 const vci_shared_mem_t *shm) {
    if (websocket_handshake(client_socket, request) != 0) {
        return;
    }

    struct timeval rcv_timeout;
    rcv_timeout.tv_sec = 0;
    rcv_timeout.tv_usec = 100000L;
    (void)setsockopt(client_socket, SOL_SOCKET, SO_RCVTIMEO,
                     (const char *)&rcv_timeout, sizeof(rcv_timeout));

    while (1) {
        /* Push the full telemetry snapshot to the connected client */
        char payload[JSON_BUF_SIZE];
        (void)memset(payload, 0, sizeof(payload));
        json_format_all_pids(shm, payload, sizeof(payload));
        if (websocket_send_text(client_socket, payload) < 0) {
            break;   /* Client disconnected */
        }

        /* Drain any control frames (close / ping) without blocking forever */
        uint8_t opcode = 0U;
        uint8_t ctrl_buf[128];
        uint32_t ctrl_len = 0U;
        while (websocket_receive(client_socket, &opcode, ctrl_buf,
                                 sizeof(ctrl_buf), &ctrl_len) == 0) {
            if (opcode == WS_OPCODE_CLOSE) {
                (void)websocket_send_close(client_socket, 1000U);
                return;
            }
        }

        (void)usleep(WS_PUSH_INTERVAL_US);
    }
}

/**
 * @brief Main diagnostic REST API endpoint router evaluating incoming HTTP requests
 */
static void web_handle_request(int32_t client_socket, const char *request, const vci_shared_mem_t *shm) {
    if ((client_socket < 0) || (request == NULL) || (shm == NULL)) {
        return;
    }

    /* WebSocket upgrade path - live telemetry streaming */
    if (strstr(request, "Sec-WebSocket-Key:") != NULL) {
        web_handle_websocket(client_socket, request, shm);
        return;
    }

    char json_buffer[JSON_BUF_SIZE];
    (void)memset(json_buffer, 0, sizeof(json_buffer));

    if (strstr(request, "GET /api/telemetry") != NULL) {
        /* Technical Synchronization Fix: Enforce maximum buffer length constraints on formatter execution */
        json_format_all_pids(shm, json_buffer, sizeof(json_buffer));
        send_json_response(client_socket, json_buffer);
    } 
    else if (strstr(request, "GET /api/status") != NULL) {
        json_format_status(shm, json_buffer, sizeof(json_buffer));
        send_json_response(client_socket, json_buffer);
    }
    else if (strstr(request, "GET /api/scan") != NULL) {
        json_format_ecu_scan(shm, json_buffer, sizeof(json_buffer));
        send_json_response(client_socket, json_buffer);
    }
    else if (strstr(request, "GET /api/vin") != NULL) {
        json_format_vehicle_info(shm, json_buffer, sizeof(json_buffer));
        send_json_response(client_socket, json_buffer);
    }
    else if (strstr(request, "GET /api/trip") != NULL) {
        json_format_trip(shm, json_buffer, sizeof(json_buffer));
        send_json_response(client_socket, json_buffer);
    }
    else if (strstr(request, "GET /api/dids") != NULL) {
        /* UDS DID registry listing (uds_did_db integration) */
        (void)snprintf(json_buffer, sizeof(json_buffer), "{");
        size_t off = strlen(json_buffer);
        uint16_t count = uds_did_count();
        for (uint16_t i = 0U; i < count; i++) {
            const uds_did_entry_t *e = uds_did_get(i);
            if (e == NULL) {
                continue;
            }
            int32_t n = snprintf(json_buffer + off, sizeof(json_buffer) - off,
                                 "%s\"0x%04X\":\"%s\"", (i > 0U) ? "," : "",
                                 e->did, e->name);
            if (n <= 0) {
                break;
            }
            off += (size_t)n;
        }
        (void)snprintf(json_buffer + off, sizeof(json_buffer) - off, "}");
        send_json_response(client_socket, json_buffer);
    }
    else if (strstr(request, "GET /api/diag/") != NULL) {
        /* Diagnostic service operations (security/variant/immo/reset/cleardtc) */
        int http_code = vci_diag_api(request, json_buffer, sizeof(json_buffer));
        if (http_code == 403) {
            const char *denied = "HTTP/1.1 403 Forbidden\r\nContent-Length: 2\r\n"
                                 "Connection: close\r\n\r\n{}";
            (void)send(client_socket, denied, strlen(denied), 0);
        } else {
            send_json_response(client_socket, json_buffer);
        }
    }
    else {
        /* Serve isolated fallback HTML index directly from code segments */
        const char *html_response = 
            "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            "<html><head><title>K-OBD-Pi Web Console</title></head>"
            "<body style='background:#0d0f12; color:#00ff66; font-family:monospace; padding:30px;'>"
            "<h1>K-OBD-PI AUTOMOTIVE ENGINE OPERATION ACTIVE</h1>"
            "<hr style='border:1px solid #262f3d;'/><div id='out'>Awaiting transmission sync...</div>"
            "<script>"
            "var ws=(window.location.protocol==='https:')?'wss://':'ws://'+location.host+'/';"
            "try{var s=new WebSocket(ws);s.onmessage=function(m){var j=JSON.parse(m.data);"
            "document.getElementById('out').innerHTML='<h3>Live: '+j.voltage+'V | Load '+j.bus_load+'% | Errors '+j.errors+'</h3>';};"
            "s.onerror=function(){location.reload();};}catch(e){"
            "setInterval(()=>{fetch('/api/status').then(r=>r.json()).then(j=>{"
            "document.getElementById('out').innerHTML=`<h3>System Voltage: ${j.voltage}V | CAN Load: ${j.bus_load}% | Faults: ${j.errors}</h3>`;})},500);}"
            "</script>"
            "</body></html>";
        (void)send(client_socket, html_response, strlen(html_response), 0);
    }
}

/**
 * @brief High-priority execution background thread initializing the HTTP daemon socket listener
 */
void *web_server_run(void *arg) {
    vci_shared_mem_t *shm = (vci_shared_mem_t *)arg;
    int32_t server_fd;
    int32_t client_fd;
    struct sockaddr_in address;
    int32_t opt = 1;
    char request_buffer[MAX_HTTP_REQUEST];

    if (shm == NULL) {
        return NULL;
    }

    config_store_t config;
    (void)memset(&config, 0, sizeof(config));
    (void)config_load(&config, WEB_CONFIG_PATH_DEFAULT);
    uint16_t web_port = (uint16_t)config_get_int(&config, "web", "port",
                                                 (int32_t)WEB_SERVER_PORT_DEFAULT);

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        fprintf(stderr, "[WEB-ERROR] Failed to allocate network streaming socket socket.\n");
        return NULL;
    }
    
    (void)setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(web_port);

    if (bind(server_fd, (const struct sockaddr *)&address, (socklen_t)sizeof(address)) < 0) {
        fprintf(stderr, "[WEB-ERROR] Bound execution mapping initialization failed on Port %u\n", web_port);
        (void)close(server_fd);
        return NULL;
    }

    if (listen(server_fd, 10) < 0) {
        (void)close(server_fd);
        return NULL;
    }
    
    printf("[WEB] Server daemon successfully initialized on standard port %u\n", web_port);

    while (1) {
        struct sockaddr_in client_address;
        socklen_t addrlen = (socklen_t)sizeof(client_address);
        
        client_fd = accept(server_fd, (struct sockaddr *)&client_address, &addrlen);
        
        if (client_fd >= 0) {
            (void)memset(request_buffer, 0, sizeof(request_buffer));
            ssize_t bytes_read = read(client_fd, request_buffer, sizeof(request_buffer) - 1U);
            
            if (bytes_read > 0) {
                request_buffer[bytes_read] = '\0';
                web_handle_request(client_fd, request_buffer, shm);
            }
            (void)close(client_fd);
        }
    }

    (void)close(server_fd);
    return NULL;
}

/* End of file web_server.c */
