CC = gcc
CFLAGS = -Wall
TARGET = can_raw_receiver

all: $(TARGET)

$(TARGET): can_raw_receiver.c
	$(CC) $(CFLAGS) -o $(TARGET) can_raw_receiver.c

clean:
	rm -f $(TARGET)
