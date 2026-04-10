# Имена на обектите за ядрото
obj-m += driver/obd_driver.o

# Пътища
KDIR := /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

# Потребителско приложение (obd_app)
# Тук добавяме пътищата към src и lib
APP_NAME = obd_app
APP_SOURCES = src/core/main.c \
              src/core/telemetry_engine.c \
              lib/obd_formulas.c \
              lib/iso_tp_stack.c

# Флагове за компилация на приложението
# -I добавя папките за заглавни файлове (.h), за да не дава грешка "file not found"
CFLAGS = -Wall -I./driver -I./lib -pthread

all:
	@echo "--- Компилиране на Kernel Модула ---"
	make -C $(KDIR) M=$(PWD) modules
	
	@echo "--- Компилиране на User-space Приложението ---"
	gcc $(CFLAGS) $(APP_SOURCES) -o $(APP_NAME)

clean:
	@echo "--- Почистване на временни файлове ---"
	make -C $(KDIR) M=$(PWD) clean
	rm -f $(APP_NAME)
	rm -f can_raw_receiver
