/*
 * pddf_custom_fpga_algo.c - driver for ds3000 Switch board FPGA I2C.
 *
 * Author: Eric Zhu
 *
 * Copyright (C) 2023 Celestica Corp.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 */

#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/pci.h>
#include <linux/kernel.h>
#include <linux/stddef.h>
#include <linux/ioport.h>
#include <linux/init.h>
#include <linux/i2c.h>
#include <linux/acpi.h>
#include <linux/io.h>
#include <linux/dmi.h>
#include <linux/slab.h>
#include <linux/err.h>
#include <linux/kobject.h>
#include <linux/platform_device.h>
#include <linux/types.h>
#include <uapi/linux/stat.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/jiffies.h>
#include "../../../../pddf/i2c/modules/include/pddf_i2c_algo.h"

extern void __iomem * fpga_ctl_addr;
extern int (*ptr_fpgapci_read)(uint32_t);
extern int (*ptr_fpgapci_write)(uint32_t, uint32_t);
extern int (*pddf_i2c_pci_add_numbered_bus)(struct i2c_adapter *, int);

#ifndef TEST_MODE
#define MOD_VERSION "0.0.1"
#else
#define MOD_VERSION "TEST"
#endif

#ifdef DEBUG_KERN
#define info(fmt,args...)  printk(KERN_INFO "line %3d : "fmt,__LINE__,##args)
#define check(REG)         printk(KERN_INFO "line %3d : %-8s = %2.2X",__LINE__,#REG,ioread8(REG));
#else
#define info(fmt,args...)
#define check(REG)
#endif

#define GET_REG_BIT(REG,BIT)   ((ioread8(REG) >> BIT) & 0x01)
#define SET_REG_BIT_H(REG,BIT) iowrite8(ioread8(REG) |  (0x01 << BIT),REG)
#define SET_REG_BIT_L(REG,BIT) iowrite8(ioread8(REG) & ~(0x01 << BIT),REG)


/* I2C_MASTER BASE ADDR */
#define I2C_MASTER_FREQ_1           0x0
#define I2C_MASTER_CTRL_1           0x4
#define I2C_MASTER_STATUS_1         0x8
#define I2C_MASTER_DATA_1           0xc
#define I2C_MASTER_PORT_ID_1        0x10

enum {
    I2C_SR_BIT_RXAK = 0,
    I2C_SR_BIT_MIF,
    I2C_SR_BIT_SRW,
    I2C_SR_BIT_BCSTM,
    I2C_SR_BIT_MAL,
    I2C_SR_BIT_MBB,
    I2C_SR_BIT_MAAS,
    I2C_SR_BIT_MCF
};

enum {
    I2C_CR_BIT_BCST = 0,
    I2C_CR_BIT_RSTA = 2,
    I2C_CR_BIT_TXAK,
    I2C_CR_BIT_MTX,
    I2C_CR_BIT_MSTA,
    I2C_CR_BIT_MIEN,
    I2C_CR_BIT_MEN,
};

enum {
    I2C_FREQ_400K = 7,
    I2C_FREQ_200K = 15,
    I2C_FREQ_100K = 31,
    I2C_FREQ_50K = 63,
};


struct fpgalogic_i2c {
    void __iomem *base;
//    u32 reg_shift;
//    u32 reg_io_width;
    wait_queue_head_t wait;
//    struct i2c_msg *msg;
//    int pos;
//    int nmsgs;
//    int state; /* see STATE_ */
//    int ip_clock_khz;
//    int bus_clock_khz;
//    void (*reg_set)(struct fpgalogic_i2c *i2c, int reg, u8 value);
//    u8 (*reg_get)(struct fpgalogic_i2c *i2c, int reg);
    u32 timeout;
    struct mutex lock;
};

static int smbus_access(struct i2c_adapter *adapter, u16 addr,
                        unsigned short flags, char rw, u8 cmd,
                        int size, union i2c_smbus_data *data);
static int i2c_wait_ack(struct i2c_adapter *a, int writing);
static int fpgai2c_init(struct fpgalogic_i2c *i2c);
static int adap_data_init(struct i2c_adapter *adap, int i2c_ch_index);


static struct fpgalogic_i2c fpgalogic_i2c[I2C_PCI_MAX_BUS];

static int i2c_wait_ack(struct i2c_adapter *a, int writing)
{
    int error = 0;
    int Status;

    struct fpgalogic_i2c *i2c = i2c_get_adapdata(a);
    unsigned long timeout;

    void __iomem *REG_FDR0;
    void __iomem *REG_CR0;
    void __iomem *REG_SR0;
    void __iomem *REG_DR0;
//    void __iomem *REG_ID0;

    REG_FDR0  = I2C_MASTER_FREQ_1   + i2c->base;
    REG_CR0   = I2C_MASTER_CTRL_1   + i2c->base;
    REG_SR0   = I2C_MASTER_STATUS_1 + i2c->base;
    REG_DR0   = I2C_MASTER_DATA_1   + i2c->base;
//    REG_ID0   = I2C_MASTER_PORT_ID_1 + i2c->base;

    check(REG_SR0);
    check(REG_CR0);

    timeout = jiffies + msecs_to_jiffies(i2c->timeout);
    while (1) {
        Status = ioread8(REG_SR0);
        if (jiffies > timeout) {
            info("Status %2.2X", Status);
            info("Error Timeout");
            error = -ETIMEDOUT;
            break;
        }


        if (Status & (1 << I2C_SR_BIT_MIF)) {
            break;
        }

        if (writing == 0 && (Status & (1 << I2C_SR_BIT_MCF))) {
            break;
        }
    }
    Status = ioread8(REG_SR0);
    iowrite8(0, REG_SR0);

    if (error < 0) {
        info("Status %2.2X", Status);
        return error;
    }

    if (!(Status & (1 << I2C_SR_BIT_MCF))) {
        info("Error Unfinish");
        return -EIO;
    }

    if (Status & (1 << I2C_SR_BIT_MAL)) {
        info("Error MAL");
        return -EAGAIN;
    }

    if (Status & (1 << I2C_SR_BIT_RXAK)) {
        info( "SL No Acknowlege");
        if (writing) {
            info("Error No Acknowlege");
            iowrite8(1 << I2C_CR_BIT_MEN, REG_CR0);
            return -ENXIO;
        }
    } else {
        info( "SL Acknowlege");
    }

    return 0;
}

static int smbus_access(struct i2c_adapter *adapter, u16 addr,
                        unsigned short flags, char rw, u8 cmd,
                        int size, union i2c_smbus_data *data)
{
    int error = 0;
    int cnt = 0;
    int bid = 0;
    struct fpgalogic_i2c *i2c;

    void __iomem *REG_FDR0;
    void __iomem *REG_CR0;
    void __iomem *REG_SR0;
    void __iomem *REG_DR0;
//    void __iomem *REG_ID0;

    /* Write the command register */
    i2c = i2c_get_adapdata(adapter);
#ifdef DEBUG_KERN
    printk(KERN_INFO "@ 0x%2.2X|f 0x%4.4X|(%d)%-5s| (%d)%-15s|CMD %2.2X "
           , addr, flags, rw, rw == 1 ? "READ " : "WRITE"
           , size,                  size == 0 ? "QUICK" :
           size == 1 ? "BYTE" :
           size == 2 ? "BYTE_DATA" :
           size == 3 ? "WORD_DATA" :
           size == 4 ? "PROC_CALL" :
           size == 5 ? "BLOCK_DATA" :
           size == 8 ? "I2C_BLOCK_DATA" :  "ERROR"
           , cmd);
#endif
    /* Map the size to what the chip understands */
    switch (size) {
        case I2C_SMBUS_QUICK:
        case I2C_SMBUS_BYTE:
        case I2C_SMBUS_BYTE_DATA:
        case I2C_SMBUS_WORD_DATA:
        case I2C_SMBUS_BLOCK_DATA:
        case I2C_SMBUS_I2C_BLOCK_DATA:
            break;
        default:
            printk(KERN_INFO "Unsupported transaction %d\n", size);
            error = -EOPNOTSUPP;
            return error;
    }

    REG_FDR0  = I2C_MASTER_FREQ_1   + i2c->base;
    REG_CR0   = I2C_MASTER_CTRL_1   + i2c->base;
    REG_SR0   = I2C_MASTER_STATUS_1 + i2c->base;
    REG_DR0   = I2C_MASTER_DATA_1   + i2c->base;
//    REG_ID0   = I2C_MASTER_PORT_ID_1 + i2c->base;

//    iowrite8(portid, REG_ID0);

    ////[S][ADDR/R]
    // Clear status register
    iowrite8(0, REG_SR0);
    iowrite8(1 << I2C_CR_BIT_MIEN |
             1 << I2C_CR_BIT_MTX |
             1 << I2C_CR_BIT_MSTA , REG_CR0);
    SET_REG_BIT_H(REG_CR0, I2C_CR_BIT_MEN);

    if (rw == I2C_SMBUS_READ &&
            (size == I2C_SMBUS_QUICK || size == I2C_SMBUS_BYTE)) {
        // sent device address with Read mode
        iowrite8(addr << 1 | 0x01, REG_DR0);
    } else {
        // sent device address with Write mode
        iowrite8(addr << 1 | 0x00, REG_DR0);
    }



    info( "MS Start");

    //// Wait {A}
    error = i2c_wait_ack(adapter, 1);
    if (error < 0) {
        info( "get error %d", error);
        goto Done;
    }

    //// [CMD]{A}
    if (size == I2C_SMBUS_BYTE_DATA ||
            size == I2C_SMBUS_WORD_DATA ||
            size == I2C_SMBUS_BLOCK_DATA ||
            size == I2C_SMBUS_I2C_BLOCK_DATA ||
            (size == I2C_SMBUS_BYTE && rw == I2C_SMBUS_WRITE)) {

        // sent command code to data register
        iowrite8(cmd, REG_DR0);
        info( "MS Send CMD 0x%2.2X", cmd);

        // Wait {A}
        error = i2c_wait_ack(adapter, 1);
        if (error < 0) {
            info( "get error %d", error);
            goto Done;
        }
    }

    switch (size) {
    case I2C_SMBUS_BYTE_DATA:
        cnt = 1;  break;
    case I2C_SMBUS_WORD_DATA:
        cnt = 2;  break;
    case I2C_SMBUS_BLOCK_DATA:
    case I2C_SMBUS_I2C_BLOCK_DATA:
        /* In block data modes keep number of byte in block[0] */
        cnt = data->block[0];
        break;
    default:
        cnt = 0;  break;
    }

    // [CNT]  used only block data write
    if (size == I2C_SMBUS_BLOCK_DATA && rw == I2C_SMBUS_WRITE) {

        iowrite8(cnt, REG_DR0);
        info( "MS Send CNT 0x%2.2X", cnt);

        // Wait {A}
        error = i2c_wait_ack(adapter, 1);
        if (error < 0) {
            info( "get error %d", error);
            goto Done;
        }
    }

    // [DATA]{A}
    if ( rw == I2C_SMBUS_WRITE && (
                size == I2C_SMBUS_BYTE ||
                size == I2C_SMBUS_BYTE_DATA ||
                size == I2C_SMBUS_WORD_DATA ||
                size == I2C_SMBUS_BLOCK_DATA ||
                size == I2C_SMBUS_I2C_BLOCK_DATA
            )) {
        bid = 0;
        info( "MS prepare to sent [%d bytes]", cnt);
        if (size == I2C_SMBUS_BLOCK_DATA || size == I2C_SMBUS_I2C_BLOCK_DATA) {
            bid = 1;    // block[0] is cnt;
            cnt += 1;   // offset from block[0]
        }
        for (; bid < cnt; bid++) {

            iowrite8(data->block[bid], REG_DR0);
            info( "   Data > %2.2X", data->block[bid]);
            // Wait {A}
            error = i2c_wait_ack(adapter, 1);
            if (error < 0) {
                goto Done;
            }
        }

    }

    // REPEATE START
    if ( rw == I2C_SMBUS_READ && (
                size == I2C_SMBUS_BYTE_DATA ||
                size == I2C_SMBUS_WORD_DATA ||
                size == I2C_SMBUS_BLOCK_DATA ||
                size == I2C_SMBUS_I2C_BLOCK_DATA
            )) {
        info( "MS Repeated Start");

        SET_REG_BIT_L(REG_CR0, I2C_CR_BIT_MEN);
        iowrite8(1 << I2C_CR_BIT_MIEN |
                 1 << I2C_CR_BIT_MTX |
                 1 << I2C_CR_BIT_MSTA |
                 1 << I2C_CR_BIT_RSTA , REG_CR0);
        SET_REG_BIT_H(REG_CR0, I2C_CR_BIT_MEN);

        // sent Address with Read mode
        iowrite8( addr << 1 | 0x1 , REG_DR0);

        // Wait {A}
        error = i2c_wait_ack(adapter, 1);
        if (error < 0) {
            goto Done;
        }

    }

    if ( rw == I2C_SMBUS_READ && (
                size == I2C_SMBUS_BYTE ||
                size == I2C_SMBUS_BYTE_DATA ||
                size == I2C_SMBUS_WORD_DATA ||
                size == I2C_SMBUS_BLOCK_DATA ||
                size == I2C_SMBUS_I2C_BLOCK_DATA
            )) {

        switch (size) {
        case I2C_SMBUS_BYTE:
        case I2C_SMBUS_BYTE_DATA:
            cnt = 1;  break;
        case I2C_SMBUS_WORD_DATA:
            cnt = 2;  break;
        case I2C_SMBUS_BLOCK_DATA:
            // will be changed after recived first data
            cnt = 3;  break;
        case I2C_SMBUS_I2C_BLOCK_DATA:
            cnt = data->block[0];  break;
        default:
            cnt = 0;  break;
        }

        bid = 0;
        info( "MS Receive");

        //set to Receive mode
        iowrite8(1 << I2C_CR_BIT_MEN |
                 1 << I2C_CR_BIT_MIEN |
                 1 << I2C_CR_BIT_MSTA , REG_CR0);

        for (bid = -1; bid < cnt; bid++) {

            // Wait for byte transfer
            error = i2c_wait_ack(adapter, 0);
            if (error < 0) {
                goto Done;
            }

            if (bid == cnt - 2) {
                info( "SET NAK");
                SET_REG_BIT_H(REG_CR0, I2C_CR_BIT_TXAK);
            }

            if (bid < 0) {
                ioread8(REG_DR0);
                info( "READ Dummy Byte" );
            } else {

                if (bid == cnt - 1) {
                    info ( "SET STOP in read loop");
                    SET_REG_BIT_L(REG_CR0, I2C_CR_BIT_MSTA);
                }
                if (size == I2C_SMBUS_I2C_BLOCK_DATA) {
                    // block[0] is read length
                    data->block[bid + 1] = ioread8(REG_DR0);
                } else {
                    data->block[bid] = ioread8(REG_DR0);
                }
                info( "DATA IN [%d] %2.2X", bid, data->block[bid]);

                if (size == I2C_SMBUS_BLOCK_DATA && bid == 0) {
                    cnt = data->block[0] + 1;
                }
            }
        }
    }

    // [P]
    SET_REG_BIT_L(REG_CR0, I2C_CR_BIT_MSTA);
    info( "MS STOP");

Done:
    iowrite8(1 << I2C_CR_BIT_MEN, REG_CR0);
    check(REG_CR0);
    check(REG_SR0);
#ifdef DEBUG_KERN
    printk(KERN_INFO "END --- Error code  %d", error);
#endif

    return error;
}

static int fpga_i2c_access(struct i2c_adapter *adapter, u16 addr,
                           unsigned short flags, char rw, u8 cmd,
                           int size, union i2c_smbus_data *data)
{
    int error = 0;
    struct fpgalogic_i2c *i2c;
    i2c = i2c_get_adapdata(adapter);

    // Acquire the master resource.
    mutex_lock(&i2c->lock);

    // Do SMBus communication
    error = smbus_access(adapter, addr, flags, rw, cmd, size, data);
    if (error < 0) {
        dev_dbg( &adapter->dev,
                 "smbus_access failed (%d) @ 0x%2.2X|f 0x%4.4X|(%d)%-5s| (%d)%-10s|CMD %2.2X "
                 , error, addr, flags, rw, rw == 1 ? "READ " : "WRITE"
                 , size,                  size == 0 ? "QUICK" :
                 size == 1 ? "BYTE" :
                 size == 2 ? "BYTE_DATA" :
                 size == 3 ? "WORD_DATA" :
                 size == 4 ? "PROC_CALL" :
                 size == 5 ? "BLOCK_DATA" :
                 size == 8 ? "I2C_BLOCK_DATA" :  "ERROR"
                 , cmd);
    }

    mutex_unlock(&i2c->lock);
    return error;
}

/**
 * A callback function show available smbus functions.
 */
static u32 fpga_i2c_func(struct i2c_adapter *a)
{
    return I2C_FUNC_SMBUS_QUICK  |
           I2C_FUNC_SMBUS_BYTE      |
           I2C_FUNC_SMBUS_BYTE_DATA |
           I2C_FUNC_SMBUS_WORD_DATA |
           I2C_FUNC_SMBUS_BLOCK_DATA |
           I2C_FUNC_SMBUS_I2C_BLOCK;
}

static const struct i2c_algorithm ds3000_i2c_algorithm = {
    .smbus_xfer = fpga_i2c_access,
    .functionality  = fpga_i2c_func,
};

static int fpgai2c_init(struct fpgalogic_i2c *i2c)
{
    iowrite8(I2C_FREQ_400K, I2C_MASTER_FREQ_1 + i2c->base );
    init_waitqueue_head(&i2c->wait);
    return 0;
};

static int adap_data_init(struct i2c_adapter *adap, int i2c_ch_index)
{
    struct fpgapci_devdata *pci_privdata = 0;
    pci_privdata = (struct fpgapci_devdata*) dev_get_drvdata(adap->dev.parent);

    if (pci_privdata == 0) {
        printk("[%s]: ERROR pci_privdata is 0\n", __FUNCTION__);
        return -1;
    }
#ifdef DEBUG_KERN
    pddf_dbg(FPGA, KERN_INFO "[%s] index: [%d] fpga_data__base_addr:0x%0x8lx"
        " fpgapci_bar_len:0x%08lx fpga_i2c_ch_base_addr:0x%08lx ch_size=0x%x supported_i2c_ch=%d",
             __FUNCTION__, i2c_ch_index, pci_privdata->fpga_data_base_addr,
            pci_privdata->bar_length, pci_privdata->fpga_i2c_ch_base_addr,
            pci_privdata->fpga_i2c_ch_size, pci_privdata->max_fpga_i2c_ch);
#endif
    if (i2c_ch_index >= pci_privdata->max_fpga_i2c_ch
            || pci_privdata->max_fpga_i2c_ch > I2C_PCI_MAX_BUS){
        printk("[%s]: ERROR i2c_ch_index=%d max_ch_index=%d out of range: %d\n",
             __FUNCTION__, i2c_ch_index, pci_privdata->max_fpga_i2c_ch, I2C_PCI_MAX_BUS);
        return -1;
    }

    memset(&fpgalogic_i2c[i2c_ch_index], 0, sizeof(fpgalogic_i2c[0]));
//    fpgalogic_i2c[i2c_ch_index].reg_shift = 0; /* 8 bit registers */
//    fpgalogic_i2c[i2c_ch_index].reg_io_width = 1; /* 8 bit read/write */
      fpgalogic_i2c[i2c_ch_index].timeout = 12; //1000;//1ms
//    fpgalogic_i2c[i2c_ch_index].ip_clock_khz = 100000;//100000;/* input clock of 100MHz */
//    fpgalogic_i2c[i2c_ch_index].bus_clock_khz = 100;
    fpgalogic_i2c[i2c_ch_index].base = pci_privdata->fpga_i2c_ch_base_addr +
                          i2c_ch_index* pci_privdata->fpga_i2c_ch_size;
    mutex_init(&fpgalogic_i2c[i2c_ch_index].lock);
    fpgai2c_init(&fpgalogic_i2c[i2c_ch_index]);

    adap->algo_data = &fpgalogic_i2c[i2c_ch_index];
    i2c_set_adapdata(adap, &fpgalogic_i2c[i2c_ch_index]);
    return 0;
}

static int pddf_i2c_pci_add_numbered_bus_ds3000 (struct i2c_adapter *adap, int i2c_ch_index)
{
    int ret = 0;

    adap_data_init(adap, i2c_ch_index);
    adap->algo  = &ds3000_i2c_algorithm;
    ret = i2c_add_numbered_adapter(adap);
    return ret;
}

/*
 * FPGAPCI APIs
 */
static int board_i2c_fpgapci_read(uint32_t offset)
{
        int data;
        data=ioread32(fpga_ctl_addr+offset);
        return data;
}


static int board_i2c_fpgapci_write(uint32_t offset, uint32_t value)
{
        iowrite32(value, fpga_ctl_addr+offset);
        return (0);
}


static int __init pddf_custom_fpga_algo_init(void)
{
    pddf_dbg(FPGA, KERN_INFO "[%s]\n", __FUNCTION__);
    pddf_i2c_pci_add_numbered_bus = &pddf_i2c_pci_add_numbered_bus_ds3000;
    ptr_fpgapci_read = board_i2c_fpgapci_read;
    ptr_fpgapci_write = board_i2c_fpgapci_write;
    return 0;
}
static void __exit pddf_custom_fpga_algo_exit(void)
{
    pddf_dbg(FPGA, KERN_INFO "[%s]\n", __FUNCTION__);
    pddf_i2c_pci_add_numbered_bus = NULL;
    ptr_fpgapci_read = NULL;
    ptr_fpgapci_write = NULL;
    return;
}

module_init(pddf_custom_fpga_algo_init);
module_exit(pddf_custom_fpga_algo_exit);

MODULE_AUTHOR("Eric Zhu <erzhu@celestica.com>");
MODULE_DESCRIPTION("Celestica ds3000 pddf fpga driver");
MODULE_VERSION(MOD_VERSION);
MODULE_LICENSE("GPL");
