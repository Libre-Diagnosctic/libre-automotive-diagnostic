/**
 * @file src/gateway/web_server.h
 * @brief Header specification for the embedded HTTP REST API gateway
 * @details Declares host configuration targets and background thread triggers
 *          for the automotive user console server node.
 * Standards: MISRA-C:2012, POSIX Threads Compliant
 */

#ifndef WEB_SERVER_H
#define WEB_SERVER_H

#include <stdint.h>

/* Environmental Embedded Network Settings */
#define HTTP_SERVER_PORT      80U
#define HTTP_MAX_PENDING_CONNS 10U
#define HTTP_BUFFER_MAX       4096U

/**
 * @brief Background execution loop interface for the web interface cluster
 * @param arg Pointer allocating the master shared memory architecture (vci_shared_mem_t)
 * @return void* Standard thread execution completion status pointer
 */
void *web_server_run(void *arg);

#endif /* WEB_SERVER_H */
