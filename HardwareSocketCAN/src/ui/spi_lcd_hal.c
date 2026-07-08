/**
 * @file src/ui/spi_lcd_hal.c
 * @brief Hardware Abstraction Layer за SPI TFT/OLED екрани (/dev/fb1)
 * @details Осигурява нискостепенен достъп до Framebuffer-а на дисплея,
 * позволявайки на Raylib да рендира директно върху SPI хардуера.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fb.h>

typedef struct {
    int fd;
    uint8_t *fbp;
    struct fb_var_screeninfo vinfo;
    struct fb_fix_screeninfo finfo;
    long screensize;
} spi_lcd_hal_t;

static spi_lcd_hal_t lcd_hal;

/**
 * @brief Инициализира достъпа до Framebuffer (/dev/fb1)
 * @return 0 при успех, -1 при грешка
 */
int vci_spi_lcd_hal_init(void) {
    /* 1. Отваряне на устройството за четене и писане */
    lcd_hal.fd = open("/dev/fb1", O_RDWR);
    if (lcd_hal.fd == -1) {
        perror("[HAL] Error opening /dev/fb1");
        return -1;
    }

    /* 2. Извличане на фиксирана информация за екрана */
    if (ioctl(lcd_hal.fd, FBIOGET_FSCREENINFO, &lcd_hal.finfo) == -1) {
        perror("[HAL] Error reading fixed information");
        close(lcd_hal.fd);
        return -1;
    }

    /* 3. Извличане на променлива информация за екрана */
    if (ioctl(lcd_hal.fd, FBIOGET_VSCREENINFO, &lcd_hal.vinfo) == -1) {
        perror("[HAL] Error reading variable information");
        close(lcd_hal.fd);
        return -1;
    }

    /* 4. Изчисляване на размера на паметта в байтове */
    lcd_hal.screensize = lcd_hal.vinfo.xres * lcd_hal.vinfo.yres * lcd_hal.vinfo.bits_per_pixel / 8;

    /* 5. Map-ване на устройството в паметта (Memory Mapping) */
    lcd_hal.fbp = (uint8_t *)mmap(0, lcd_hal.screensize, PROT_READ | PROT_WRITE, MAP_SHARED, lcd_hal.fd, 0);
    
    if ((intptr_t)lcd_hal.fbp == -1) {
        perror("[HAL] Failed to map framebuffer device to memory");
        close(lcd_hal.fd);
        return -1;
    }

    printf("[HAL] SPI LCD mapped: %dx%d, %dbpp, size: %ld bytes\n", 
           lcd_hal.vinfo.xres, lcd_hal.vinfo.yres, lcd_hal.vinfo.bits_per_pixel, lcd_hal.screensize);
    
    return 0;
}

/**
 * @brief Почистване на екрана (Clear Screen) на хардуерно ниво
 */
void vci_spi_lcd_hal_clear(uint16_t color_rgb565) {
    if (!lcd_hal.fbp) return;
    
    uint16_t *ptr = (uint16_t *)lcd_hal.fbp;
    uint32_t num_pixels = lcd_hal.vinfo.xres * lcd_hal.vinfo.yres;
    
    for (uint32_t i = 0; i < num_pixels; i++) {
        ptr[i] = color_rgb565;
    }
}

/**
 * @brief Затваряне на HAL слоя
 */
void vci_spi_lcd_hal_close(void) {
    if (lcd_hal.fbp) {
        munmap(lcd_hal.fbp, lcd_hal.screensize);
    }
    if (lcd_hal.fd != -1) {
        close(lcd_hal.fd);
    }
}
