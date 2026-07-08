/**
 * @file src/ui/dashboard_render.c (Extension: Oscilloscope Module)
 * @brief Real-time Oscilloscope Visualization for HDMI Dashboard
 * @details Добавя графичен слой за визуализация на сурови сигнали (Scope) с честота до 1kHz.
 */

#include "raylib.h"
#include "../../driver/obd_ioctl.h"

#define SCOPE_HISTORY_SIZE 512
#define SCOPE_HEIGHT       150
#define SCOPE_WIDTH        760

static float scope_buffer[SCOPE_HISTORY_SIZE] = { 0 };
static int scope_ptr = 0;

/**
 * @brief Рендира осцилоскопна мрежа и сигнал в реално време
 * @param x Позиция X
 * @param y Позиция Y
 * @param sample Нова проба (напр. от ламбда сонда или дебитомер)
 */
void DrawDashboardScope(int x, int y, float sample) {
    /* 1. Обновяване на цикличния буфер */
    scope_buffer[scope_ptr] = sample;
    scope_ptr = (scope_ptr + 1) % SCOPE_HISTORY_SIZE;

    /* 2. Рендиране на фонова мрежа */
    DrawRectangle(x, y, SCOPE_WIDTH, SCOPE_HEIGHT, (Color){ 20, 20, 25, 200 });
    for (int i = 0; i <= 10; i++) {
        DrawLine(x + (i * SCOPE_WIDTH / 10), y, x + (i * SCOPE_WIDTH / 10), y + SCOPE_HEIGHT, (Color){ 40, 40, 45, 255 });
        DrawLine(x, y + (i * SCOPE_HEIGHT / 10), x + SCOPE_WIDTH, y + (i * SCOPE_HEIGHT / 10), (Color){ 40, 40, 45, 255 });
    }

    /* 3. Рендиране на сигнала (Line Strip) */
    for (int i = 0; i < SCOPE_HISTORY_SIZE - 1; i++) {
        int idx1 = (scope_ptr + i) % SCOPE_HISTORY_SIZE;
        int idx2 = (scope_ptr + i + 1) % SCOPE_HISTORY_SIZE;
        
        /* Мащабиране на сигнала (нормализирано спрямо височината) */
        float val1 = y + SCOPE_HEIGHT - (scope_buffer[idx1] * 10.0f); 
        float val2 = y + SCOPE_HEIGHT - (scope_buffer[idx2] * 10.0f);

        DrawLine(x + (i * SCOPE_WIDTH / SCOPE_HISTORY_SIZE), val1, 
                 x + ((i + 1) * SCOPE_WIDTH / SCOPE_HISTORY_SIZE), val2, GREEN);
    }
    
    DrawText("REAL-TIME SIGNAL SCOPE", x + 10, y + 10, 12, DARKGRAY);
}
