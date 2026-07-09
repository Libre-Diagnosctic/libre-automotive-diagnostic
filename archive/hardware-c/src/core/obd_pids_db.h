/**
 * @file pid_db.c
 * @brief Dictionary-driven PID Lookup Table.
 */

#include "obd_pids_db.h"
#include "obd_formulas.h" // Прототипи на формулите от предишната стъпка

/**
 * @brief Пълна дефиниция на системните PIDs
 * Използваме статична алокация съгласно MISRA.
 */
const obd_pid_definition_t MASTER_PID_TABLE[] = {
    {0x01, 0x0C, 2, "Engine RPM", "rpm", formula_rpm},
    {0x01, 0x0D, 1, "Vehicle Speed", "km/h", formula_speed},
    {0x01, 0x05, 1, "Coolant Temp", "°C", formula_temp},
    {0x01, 0x10, 2, "MAF Rate", "g/s", formula_maf},
    {0x01, 0x11, 1, "Throttle Pos", "%", formula_percent},
    {0x01, 0x42, 2, "Battery Voltage", "V", formula_module_voltage}
};

const uint32_t MASTER_PID_COUNT = sizeof(MASTER_PID_TABLE) / sizeof(obd_pid_definition_t);
