/**
 * @file src/ui/dashboard_render.c
 * @brief Dashboard / Oscilloscope rendering layer.
 * @details Provides the raylib-aware oscilloscope widget plus a headless
 *          dashboard thread that keeps the trip registers in shared memory
 *          up to date (required for linking the master orchestrator).
 * @copyright 2026 K-OBD-Pi Automotive Systems Architect. All rights reserved.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "../../driver/obd_ioctl.h"

#define SCOPE_HISTORY_SIZE 512
#define SCOPE_HEIGHT       150
#define SCOPE_WIDTH        760

static float scope_buffer[SCOPE_HISTORY_SIZE] = { 0 };
static int scope_ptr = 0;

/**
 * @brief Pushes a sample into the circular scope buffer
 */
void vci_scope_push(float sample) {
    scope_buffer[scope_ptr] = sample;
    scope_ptr = (scope_ptr + 1) % SCOPE_HISTORY_SIZE;
}

/**
 * @brief Copies the linearized scope data into an output buffer
 */
void vci_scope_get_data(float *out, uint32_t count) {
    if ((out == NULL) || (count > SCOPE_HISTORY_SIZE)) {
        return;
    }
    for (uint32_t i = 0U; i < count; i++) {
        out[i] = scope_buffer[(scope_ptr + i) % SCOPE_HISTORY_SIZE];
    }
}

#ifdef RAYLIB_H
/**
 * @brief Renders the oscilloscope grid and signal (requires raylib)
 */
void DrawDashboardScope(int x, int y, float sample) {
    vci_scope_push(sample);

    DrawRectangle(x, y, SCOPE_WIDTH, SCOPE_HEIGHT, (Color){ 20, 20, 25, 200 });
    for (int i = 0; i <= 10; i++) {
        DrawLine(x + (i * SCOPE_WIDTH / 10), y, x + (i * SCOPE_WIDTH / 10), y + SCOPE_HEIGHT, (Color){ 40, 40, 45, 255 });
        DrawLine(x, y + (i * SCOPE_HEIGHT / 10), x + SCOPE_WIDTH, y + (i * SCOPE_HEIGHT / 10), (Color){ 40, 40, 45, 255 });
    }

    for (int i = 0; i < SCOPE_HISTORY_SIZE - 1; i++) {
        int idx1 = (scope_ptr + i) % SCOPE_HISTORY_SIZE;
        int idx2 = (scope_ptr + i + 1) % SCOPE_HISTORY_SIZE;

        float val1 = y + SCOPE_HEIGHT - (scope_buffer[idx1] * 10.0f);
        float val2 = y + SCOPE_HEIGHT - (scope_buffer[idx2] * 10.0f);

        DrawLine(x + (i * SCOPE_WIDTH / SCOPE_HISTORY_SIZE), (int)val1,
                 x + ((i + 1) * SCOPE_WIDTH / SCOPE_HISTORY_SIZE), (int)val2, GREEN);
    }

    DrawText("REAL-TIME SIGNAL SCOPE", x + 10, y + 10, 12, DARKGRAY);
}
#endif

/**
 * @brief Headless dashboard thread: feeds the oscilloscope from the latest
 *        RPM sample. Trip register ownership belongs to the telemetry engine
 *        (single-writer invariant - see telemetry_engine.c step 8).
 * @param arg Pointer to the vci_shared_mem_t zero-copy region
 */
void *dashboard_render_run(void *arg) {
    vci_shared_mem_t *shm = (vci_shared_mem_t *)arg;
    if (shm == NULL) {
        return NULL;
    }

    printf("[UI] Dashboard render thread started.\n");

    while (1) {
        /* Feed scope with engine RPM if available */
        if (shm->pid_db[0x0C].is_valid != 0U) {
            vci_scope_push(shm->pid_db[0x0C].calculated_value);
        }

        (void)usleep(50000);   /* 20 Hz UI tick */
    }

    return NULL;
}

/* End of file dashboard_render.c */
