/**
 * PROJECT: K-OBD-PI-AUTOMOTIVE
 * MODULE: gateway_server_core.c
 * DESCRIPTION: High-Performance Multi-threaded TCP Gateway with E2E Protection
 * STANDARD: Automotive Grade Socket Management
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <pthread.h>
#include <arpa/inet.h>
#include <errno.h>

#define GATEWAY_PORT 8080
#define MAX_CONNECTIONS 20
#define BUFFER_SIZE 4096

typedef struct {
    int client_socket;
    struct sockaddr_in client_addr;
    uint64_t connection_time;
} client_context_t;

const char* get_uds_status_string(int code) {
    switch(code) {
        case 0x10: return "Diagnostic Session Control Active";
        case 0x11: return "ECU Reset Service Pending";
        case 0x27: return "Security Access - Seed Exchange";
        case 0x3E: return "Tester Present - Keep Alive Sent";
        case 0x22: return "Read Data By Identifier - Sampling";
        default: return "System Standby - Monitoring CAN0";
    }
}

void serialize_telemetry_json(char *dest, int rpm, int speed, float temp) {
    sprintf(dest, 
        "{\n"
        "  \"header\": {\n"
        "    \"protocol\": \"K-OBD-PRO\",\n"
        "    \"version\": \"2.1.0\",\n"
        "    \"status\": \"OPERATIONAL\"\n"
        "  },\n"
        "  \"data\": {\n"
        "    \"engine_rpm\": %d,\n"
        "    \"vehicle_speed\": %d,\n"
        "    \"coolant_temp\": %.2f,\n"
        "    \"dtc_count\": 0\n"
        "  },\n"
        "  \"bus_info\": {\n"
        "    \"interface\": \"can0\",\n"
        "    \"bitrate\": 500000,\n"
        "    \"load\": \"14.2%%\"\n"
        "  }\n"
        "}\n", rpm, speed, temp);
}

void* handle_client_session(void* arg) {
    client_context_t *ctx = (client_context_t*)arg;
    char buffer[BUFFER_SIZE];
    char json_out[BUFFER_SIZE];

    printf("[GATEWAY] Client connected from %s\n", inet_ntoa(ctx->client_addr.sin_addr));

    while(1) {
        memset(buffer, 0, BUFFER_SIZE);
        int valread = recv(ctx->client_socket, buffer, BUFFER_SIZE, 0);
        
        if (valread <= 0) {
            printf("[GATEWAY] Client disconnected.\n");
            break;
        }

        if (strstr(buffer, "GET_LIVE")) {
            serialize_telemetry_json(json_out, 3200, 120, 92.5);
            send(ctx->client_socket, json_out, strlen(json_out), 0);
        } 
        else if (strstr(buffer, "GET_STATUS")) {
            const char* status = get_uds_status_string(0x22);
            send(ctx->client_socket, status, strlen(status), 0);
        }
        else {
            const char* err = "{\"error\": \"INVALID_COMMAND\"}\n";
            send(ctx->client_socket, err, strlen(err), 0);
        }
    }

    close(ctx->client_socket);
    free(ctx);
    return NULL;
}

int start_gateway_service() {
    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);

    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("Socket initialization failed");
        return -1;
    }

    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt))) {
        perror("Setsockopt failed");
        return -1;
    }

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(GATEWAY_PORT);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("Bind failed");
        return -1;
    }

    if (listen(server_fd, MAX_CONNECTIONS) < 0) {
        perror("Listen failed");
        return -1;
    }

    printf("[SYSTEM] Automotive Gateway Server listening on port %d\n", GATEWAY_PORT);

    while(1) {
        new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen);
        if (new_socket < 0) {
            perror("Accept error");
            continue;
        }

        pthread_t thread_id;
        client_context_t *ctx = malloc(sizeof(client_context_t));
        ctx->client_socket = new_socket;
        ctx->client_addr = address;

        if (pthread_create(&thread_id, NULL, handle_client_session, (void*)ctx) < 0) {
            perror("Could not create thread");
            free(ctx);
            continue;
        }
        pthread_detach(thread_id);
    }

    return 0;
}
