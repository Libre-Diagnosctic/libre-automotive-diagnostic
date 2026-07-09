/**
 * @file secure_server.c
 * @brief Hardened Binary TCP API Gateway (TLS 1.3 Secured Server Subsystem)
 * @details Establishes encrypted end-to-end communication channels via OpenSSL.
 *          Implements robust input validation and mitigates network resource leakage.
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <pthread.h>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include "../../driver/obd_ioctl.h"

#define SECURE_API_PORT       8888U
#define MAX_PENDING_CONNS     5U
#define AUTH_TOKEN_EXPECTED   "K-OBD-VCI-PRO-2026"
#define PACKET_SYNC_WORD      0xAA55AA55U

/* External robust CRC32 provider engine link */
extern uint32_t crc32_compute(const uint8_t *data, uint32_t length);

#pragma pack(push, 1)
typedef struct {
    uint32_t sync_word;   /* Diagnostic identifier framing token: 0xAA55AA55 */
    uint16_t version;     /* API Core operational version ledger entry */
    uint16_t command_id;  /* Service dispatch token: 0x01 = Telemetry, 0x02 = Scan */
    uint32_t payload_len; /* Dynamic length specification boundary checker */
    uint8_t  payload[2048];
    uint32_t crc32;       /* Integrity confirmation parameter verification value */
} vci_api_packet_t;
#pragma pack(pop)

typedef struct {
    int32_t socket_fd;
    SSL     *ssl_context;
} client_session_t;

/**
 * @brief Process encrypted client requests via isolation background thread execution path
 */
static void *vci_handle_secure_client(void *arg) {
    client_session_t *session = (client_session_t *)arg;
    if (session == NULL) {
        return NULL;
    }

    int32_t client_sock = session->socket_fd;
    SSL *ssl = session->ssl_context;
    uint8_t buffer[sizeof(vci_api_packet_t)];

    printf("[SECURE-SERVER] Dynamic TLS 1.3 handshake requested on Socket: %d\n", client_sock);

    /* 1. Execute Cryptographic Handshake via OpenSSL Core Pipeline */
    if (SSL_accept(ssl) <= 0) {
        fprintf(stderr, "[SECURE-SERVER-ERROR] TLS handshake initialization failed. Aborting connection.\n");
        SSL_free(ssl);
        (void)close(client_sock);
        free(session);
        return NULL;
    }

    /* 2. Authentication Protocol Evaluation Step */
    (void)memset(buffer, 0, sizeof(buffer));
    int32_t read_bytes = (int32_t)SSL_read(ssl, buffer, 64);
    
    if ((read_bytes <= 0) || (strncmp((const char*)buffer, AUTH_TOKEN_EXPECTED, strlen(AUTH_TOKEN_EXPECTED)) != 0)) {
        fprintf(stderr, "[SECURE-SERVER] Access token authentication verification mismatch. Closing link.\n");
        SSL_free(ssl);
        (void)close(client_sock);
        free(session);
        return NULL;
    }

    printf("[SECURE-SERVER] Authentication verification success. Channel encryption established.\n");

    /* 3. High-Performance Bounded Command Processing Loop */
    while (1) {
        (void)memset(buffer, 0, sizeof(buffer));
        read_bytes = (int32_t)SSL_read(ssl, buffer, (int)sizeof(vci_api_packet_t));
        if (read_bytes <= 0) {
            break; /* Client socket disconnected cleanly or connection lost */
        }

        /* Safe structural evaluation to satisfy alignment and array bounds bounds checking */
        if ((size_t)read_bytes >= (sizeof(vci_api_packet_t) - 2048U)) {
            vci_api_packet_t pkt;
            (void)memcpy(&pkt, buffer, sizeof(vci_api_packet_t));

            /* Confirm synchronization identifier sequence boundaries */
            if (pkt.sync_word == PACKET_SYNC_WORD) {
                if (pkt.payload_len <= 2048U) {
                    /* Perform validation execution pass over payload bytes */
                    uint32_t calc_crc = crc32_compute(pkt.payload, pkt.payload_len);
                    if (calc_crc == pkt.crc32) {
                        
                        /* 4. Service Identification Routing Logic */
                        switch (pkt.command_id) {
                            case 0x01U: /* Dynamic Data Telemetry Frame Request */
                                (void)SSL_write(ssl, "ACK_TELEMETRY_SYNC", 18);
                                break;
                            case 0x02U: /* Network Diagnostic Topology Global Scan Trigger */
                                (void)SSL_write(ssl, "ACK_SCAN_ENGAGED", 16);
                                break;
                            default:
                                (void)SSL_write(ssl, "ERR_UNKNOWN_CMD", 15);
                                break;
                        }
                    } else {
                        fprintf(stderr, "[SECURE-SERVER] Warning: Packet dropped due to integrity CRC32 mismatch.\n");
                    }
                }
            }
        }
    }

    printf("[SECURE-SERVER] Termination request processed. Freeing cryptographic stream resources.\n");
    SSL_free(ssl);
    (void)close(client_sock);
    free(session);
    return NULL;
}

/**
 * @brief Thread runner initializing the OpenSSL pipeline and tracking standard interface bindings
 */
void *secure_server_run(void *arg) {
    (void)arg; /* Suppress unused initialization thread token warning under -Werror */
    int32_t server_fd;
    struct sockaddr_in address;
    int32_t opt = 1;

    /* 1. Global OpenSSL Core Cryptographic Layer Context Allocation and Hardening Setup */
    SSL_library_init();
    OpenSSL_add_all_algorithms();
    SSL_load_error_strings();

    const SSL_METHOD *method = TLS_server_method();
    SSL_CTX *ctx = SSL_CTX_new(method);
    if (ctx == NULL) {
        fprintf(stderr, "[SECURE-SERVER-ERROR] Unable to build secure OpenSSL context environment.\n");
        return NULL;
    }

    /* Enforce strict encryption profile settings matching TLS 1.3 specifications */
    (void)SSL_CTX_set_min_proto_version(ctx, TLS1_3_VERSION);

    /* 2. Initialize Hardware Boundary Network Sockets */
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        SSL_CTX_free(ctx);
        return NULL;
    }
    
    (void)setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(SECURE_API_PORT);

    if (bind(server_fd, (const struct sockaddr *)&address, (socklen_t)sizeof(address)) < 0) {
        fprintf(stderr, "[SECURE-SERVER-ERROR] Address binding failed on target binary port %u\n", SECURE_API_PORT);
        (void)close(server_fd);
        SSL_CTX_free(ctx);
        return NULL;
    }

    if (listen(server_fd, (int)MAX_PENDING_CONNS) < 0) {
        (void)close(server_fd);
        SSL_CTX_free(ctx);
        return NULL;
    }

    printf("[SECURE-SERVER] Operational TLS 1.3 daemon initialized on binary API port %u\n", SECURE_API_PORT);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = (socklen_t)sizeof(client_addr);
        int32_t new_fd = accept(server_fd, (struct sockaddr *)&client_addr, &addr_len);

        if (new_fd >= 0) {
            client_session_t *session = malloc(sizeof(client_session_t));
            if (session != NULL) {
                session->socket_fd = new_fd;
                session->ssl_context = SSL_new(ctx);

                if (session->ssl_context != NULL) {
                    SSL_set_fd(session->ssl_context, new_fd);
                    
                    pthread_t tid;
                    if (pthread_create(&tid, NULL, vci_handle_secure_client, session) == 0) {
                        (void)pthread_detach(tid);
                    } else {
                        SSL_free(session->ssl_context);
                        (void)close(new_fd);
                        free(session);
                    }
                } else {
                    (void)close(new_fd);
                    free(session);
                }
            } else {
                (void)close(new_fd);
            }
        }
    }

    (void)close(server_fd);
    SSL_CTX_free(ctx);
    return NULL;
}

/* End of file secure_server.c */
