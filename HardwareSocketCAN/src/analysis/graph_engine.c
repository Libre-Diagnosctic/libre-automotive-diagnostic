/**
 * @file src/analysis/graph_engine.c
 * @brief Професионален Real-time Oscilloscope (Scope) за анализ на сигнали
 * @details Реализира логика за буфериране на високочестотни данни и тяхната 
 * подготовка за графична визуализация. Поддържа тригериране и мащабиране.
 */

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "../../driver/obd_ioctl.h"

#define GRAPH_BUFFER_SIZE 1024
#define SCOPE_CHANNELS    4

typedef struct {
    float samples[GRAPH_BUFFER_SIZE];
    uint32_t head;
    float trigger_level;
    bool trigger_armed;
    float scale_factor;
} scope_channel_t;

static scope_channel_t scope_state[SCOPE_CHANNELS];

/**
 * @brief Добавя нова точка към осцилоскопа
 * @param channel_idx Индекс на канала (0-3)
 * @param value Физическа стойност (напр. Волтаж или RPM)
 */
void graph_engine_push_sample(uint8_t channel_idx, float value) {
    if (channel_idx >= SCOPE_CHANNELS) return;
    
    scope_channel_t *ch = &scope_state[channel_idx];
    
    /* Zero-copy logic: директен запис в цикличен буфер */
    ch->samples[ch->head] = value;
    
    /* Проста логика за тригериране (Rising Edge) */
    if (!ch->trigger_armed && value > ch->trigger_level) {
        ch->trigger_armed = true;
        /* Маркиране на събитието в телеметрията */
    }
    
    ch->head = (ch->head + 1) % GRAPH_BUFFER_SIZE;
}

/**
 * @brief Извлича линеен масив от проби за рендиране в UI
 * @param channel_idx Индекс
 * @param out_buffer Изходящ буфер (трябва да е с размер GRAPH_BUFFER_SIZE)
 */
void graph_engine_get_linear_data(uint8_t channel_idx, float *out_buffer) {
    if (channel_idx >= SCOPE_CHANNELS) return;
    
    scope_channel_t *ch = &scope_state[channel_idx];
    uint32_t current_head = ch->head;

    /* Сглобяване на цикличния буфер в линеен масив */
    for (uint32_t i = 0; i < GRAPH_BUFFER_SIZE; i++) {
        out_buffer[i] = ch->samples[(current_head + i) % GRAPH_BUFFER_SIZE];
    }
}

/**
 * @brief Автоматично изчислява мащаба (Auto-scale) на базата на мин/макс стойности
 */
void graph_engine_auto_scale(uint8_t channel_idx) {
    scope_channel_t *ch = &scope_state[channel_idx];
    float max_val = -1e9, min_val = 1e9;

    for (int i = 0; i < GRAPH_BUFFER_SIZE; i++) {
        if (ch->samples[i] > max_val) max_val = ch->samples[i];
        if (ch->samples[i] < min_val) min_val = ch->samples[i];
    }

    float range = max_val - min_val;
    ch->scale_factor = (range > 0) ? (1.0f / range) : 1.0f;
}

/* Край на файл graph_engine.c */
