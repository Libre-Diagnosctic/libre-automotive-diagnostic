# ============================================================================
#  K-OBD-PI AUTOMOTIVE - Master Build System
#  Builds: kernel module (obd_vci) + user-space gateway + CLI tools + libs
# ============================================================================

CC      := gcc
CFLAGS  := -Wall -Wextra -O2 -std=gnu11 -I. -Idriver -Ilib -Isrc/core -Isrc/gateway -pthread
LDFLAGS := -lm -pthread

KDIR := /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

# ----------------------------------------------------------------------------
# Libraries
# ----------------------------------------------------------------------------
LIB_SRCS := \
	lib/obd_formulas.c \
	lib/obd_pids_db.c \
	lib/iso_tp_stack.c \
	lib/uds_iso14229.c \
	lib/crc_provider.c \
	lib/crypto_auth.c \
	lib/vin_decoder.c \
	lib/token_auth_mgr.c \
	lib/j2534_runtime.c \
	lib/doip_iso13400.c \
	lib/wwh_obd_stack.c \
	lib/obd_dtc_decoder.c \
	lib/config_loader.c \
	lib/logging.c \
	lib/trip_logger.c \
	lib/can_stats.c \
	lib/mqtt_client.c \
	lib/daemon_utils.c \
	lib/watchdog.c \
	lib/self_test.c \
	lib/remote_bridge.c \
	lib/remote_vci_bridge.c \
	lib/dbc_parser.c \
	lib/j1939_stack.c \
	lib/uds_did_db.c \
	lib/websocket_server.c \
	lib/can_recorder.c \
	lib/can_replay.c \
	lib/sgw_policy_engine.c \
	lib/csv_exporter.c \
	lib/vehicle_profiles.c

# ----------------------------------------------------------------------------
# Core gateway application (master orchestrator)
# ----------------------------------------------------------------------------
APP_SRCS := \
	src/core/main.c \
	src/core/telemetry_engine.c \
	src/core/global_scan_engine.c \
	src/core/health_monitor.c \
	src/core/variant_coding.c \
	src/core/security_unlock.c \
	src/core/immo_keygen.c \
	src/core/doip_activator.c \
	src/gateway/web_server.c \
	src/gateway/json_formatter.c \
	src/ui/dashboard_render.c \
	src/analysis/analysis_engine.c \
	src/analysis/battery_health.c \
	src/analysis/graph_engine.c \
	src/analysis/trip_statistics.c

APP_OBJS := $(APP_SRCS:.c=.o)
LIB_OBJS := $(LIB_SRCS:.c=.o)

# ----------------------------------------------------------------------------
# Targets
# ----------------------------------------------------------------------------
all: module gateway tools

module:
	@echo "--- Compiling kernel module ---"
	make -C $(KDIR) M=$(PWD)/driver modules
	@echo "--- Done: driver/obd_driver.ko ---"

gateway: obd_app

obd_app: $(APP_OBJS) $(LIB_OBJS)
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)
	@echo "--- Built obd_app ---"

tools: obd_cli can_raw_receiver obd_user_app

obd_cli: main.c $(LIB_OBJS)
	$(CC) $(CFLAGS) main.c $(LIB_OBJS) -o $@ $(LDFLAGS)

can_raw_receiver: can_raw_receiver.c
	$(CC) $(CFLAGS) can_raw_receiver.c -o $@ $(LDFLAGS)

obd_user_app: user-app/main.c $(LIB_OBJS)
	$(CC) $(CFLAGS) user-app/main.c $(LIB_OBJS) -o $@ $(LDFLAGS)

# Optional targets requiring external dependencies
secure_server: src/gateway/secure_server.c $(LIB_OBJS)
	$(CC) $(CFLAGS) -lssl -lcrypto src/gateway/secure_server.c $(LIB_OBJS) -o secure_server $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	@echo "--- Cleaning ---"
	-rm -f obd_app obd_cli can_raw_receiver obd_user_app secure_server
	-find . -name '*.o' -delete
	-find . -name '*.ko' -delete
	-find . -name '*.mod.c' -delete
	-find . -name '*.mod' -delete
	-find . -name '*.order' -delete
	-find . -name '*.symvers' -delete
	-rm -rf driver/.tmp_versions
	make -C $(KDIR) M=$(PWD)/driver clean 2>/dev/null || true

.PHONY: all module gateway tools obd_app clean secure_server
