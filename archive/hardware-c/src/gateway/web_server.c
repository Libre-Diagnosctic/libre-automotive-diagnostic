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
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include "../../driver/obd_ioctl.h"
#include "json_formatter.h"

#define WEB_SERVER_PORT  80U
#define MAX_HTTP_REQUEST 2048U
#define JSON_BUF_SIZE    4096U

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
 * @brief Main diagnostic REST API endpoint router evaluating incoming HTTP requests
 */
static void web_handle_request(int32_t client_socket, const char *request, const vci_shared_mem_t *shm) {
    if ((client_socket < 0) || (request == NULL) || (shm == NULL)) {
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
        /* Package core system tracking registries from shared memory regions into raw JSON */
        int32_t written = snprintf(json_buffer, sizeof(json_buffer), 
                "{\"voltage\":%.2f,\"bus_load\":%u,\"errors\":%u,\"ignition\":%s}",
                (double)shm->battery_voltage, 
                (unsigned int)shm->bus_load_pct, 
                (unsigned int)shm->error_count, 
                (shm->ignition_on != 0U) ? "true" : "false");
                
        if ((written > 0) && ((size_t)written < sizeof(json_buffer))) {
            send_json_response(client_socket, json_buffer);
        }
    }
    else {
        /* Serve isolated fallback HTML index directly from code segments */
        const char *html_response = 
            "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            "<html><head><title>K-OBD-Pi Web Console</title></head>"
            "<body style='background:#0d0f12; color:#00ff66; font-family:monospace; padding:30px;'>"
            "<h1>🚀 K-OBD-PI AUTOMOTIVE ENGINE OPERATION ACTIVE</h1>"
            "<hr style='border:1px solid #262f3d;'/><div id='out'>Awaiting transmission sync...</div>"
            "<script>setInterval(()=>{fetch('/api/status').then(r=>r.json()).then(j=>{"
            "document.getElementById('out').innerHTML=`<h3>System Voltage: ${j.voltage}V | CAN Load: ${j.bus_load}% | Faults: ${j.errors}</h3>`;})},500);</script>"
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

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        fprintf(stderr, "[WEB-ERROR] Failed to allocate network streaming socket socket.\n");
        return NULL;
    }
    
    (void)setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(WEB_SERVER_PORT);

    if (bind(server_fd, (const struct sockaddr *)&address, (socklen_t)sizeof(address)) < 0) {
        fprintf(stderr, "[WEB-ERROR] Bound execution mapping initialization failed on Port %u\n", WEB_SERVER_PORT);
        (void)close(server_fd);
        return NULL;
    }

    if (listen(server_fd, 10) < 0) {
        (void)close(server_fd);
        return NULL;
    }
    
    printf("[WEB] Server daemon successfully initialized on standard port %u\n", WEB_SERVER_PORT);

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
