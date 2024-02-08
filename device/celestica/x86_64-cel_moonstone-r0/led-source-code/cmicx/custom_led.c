/*
 * $Id: custom_led.c$
 * $Copyright: (c) 2022 Broadcom.
 * Broadcom Proprietary and Confidential. All rights reserved.$
 *
 * File:        custom_led.c
 * Purpose:     Customer CMICx LED bit pattern composer.
 * Requires:
 */

/******************************************************************************
 *
 * The CMICx LED interface has two RAM Banks as shown below, Bank0
 * (Accumulation RAM) for accumulation of status from ports and Bank1
 * (Pattern RAM) for writing LED pattern. Both Bank0 and Bank1 are of
 * 1024x16-bit, each row representing one port.
 *
 *           Accumulation RAM (Bank 0)        Pattern RAM (Bank1)
 *          15                       0     15                          0
 *         ----------------------------   ------------------------------
 * Row 0   |  led_uc_port 0 status    |   | led_uc_port 0 LED Pattern   |
 *         ----------------------------   ------------------------------
 * Row 1   |  led_uc_port 1 status    |   | led_uc_port 1 LED Pattern   |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 * Row 127 |  led_uc_port 128 status  |   | led_uc_port 128 LED Pattern |
 *         ----------------------------   ------------------------------
 * Row 128 |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 * Row x   |  led_uc_port (x+1) status|   | led_uc_port(x+1) LED Pattern|
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 *         |                          |   |                             |
 *         ----------------------------   ------------------------------
 * Row 1022|  led_uc_port 1022 status |   | led_uc_port 1022 LED Pattern|
 *         ----------------------------   ------------------------------
 * Row 1023|  led_uc_port 1023 status |   | led_uc_port 1023 LED Pattern|
 *         ----------------------------   ------------------------------
 *
 * Format of Accumulation RAM:
 *
 * Bits   15:9       8        7         6        5      4:3     2    1    0
 *    ------------------------------------------------------------------------
 *    | Reserved | Link  | Link-up |  Flow  | Duplex | Speed | Col | Tx | Rx |
 *    |          | Enable| Status  | Control|        |       |     |    |    |
 *    ------------------------------------------------------------------------
 *
 * Where Speed 00 - 10 Mbps
 *             01 - 100 Mbps
 *             10 - 1 Gbps
 *             11 - Above 1 Gbps
 *
 * The customer handler in this file should read the port status from
 * the HW Accumulation RAM or "led_control_data" array, then form the required
 * LED bit pattern in the Pattern RAM at the corresponding location.
 *
 * The "led_control_data" is a 1024 bytes array, application user can use BCM LED API
 * to exchange port information with LED FW.
 *
 * Typically, led_uc_port = physical port number - constant.
 * The constant is 1 for ESW chips, 0 for DNX/DNXF chips and 2 for Firelight.
 * For those ports that do not meet the above rule, they will be listed in
 * "include/shared/cmicfw/cmicx_led_public.h".
 *
 * There are five LED interfaces in CMICx-based devices, and although
 * a single interface can be used to output LED patterns for all
 * ports, it is possible to use more than one interface, e.g. the LEDs
 * for some ports are connected to LED interface-0, while the rest of
 * the ports are connected to LED interface-1. Accordingly, the custom
 * handler MUST fill in start-port, end-port and pattern-width in the
 * soc_led_custom_handler_ctrl_t structure passed to the custom
 * handler.
 *
 * The example custom handler provided in this file has reference code
 * for forming two different LED patterns. Please refer to these
 * patterns before writing your own custom handler code.
 *
 * The led_customer_t structure definition is available in
 * include/shared/cmicfw/cmicx_led_public.h.
 *
 ******************************************************************************/

#include <shared/cmicfw/cmicx_led_public.h>

/*****************************************
 *  Customer defintion.
 *****************************************/

#define LANE_SPEED_1G                    0
#define LANE_SPEED_10G                   1
#define LANE_SPEED_25G                   2
#define LANE_SPEED_50G                   3
#define LANE_SPEED_100G                  4

/*! The led behavior & bitstream */
#define LED_BIT_GREEN                    0b00
#define LED_BIT_AMBER                    0b01
#define LED_BIT_BLACK                    0b11
#define LED_BLINK_GREEN                  0xF0
#define LED_BLINK_AMBER                  0xF1
#define IS_BLINK_MODE(c)                 ((c & 0xF0) == 0xF0)
#define GET_BLINK_COLOR(c)               (c & 0x0F)

/*! Compression mode, define the number of lane status mapping to one color group */
#define COMPRESS_MODE                    4

/*! The time window of activity LED displaying on */
#define ACT_TICKS                        2

/*! OSFP ports defined software flag. */
#define LED_SW_LINK_UP                   0x1

/*! mgnt ports defined software flag. */
#define LED_HW_LINK                      0x100

/*! define the max physical port number used, include mgnt. */
#define MAX_LED_UC_PORT                  514

/*! define the max physical port number for mgnt */
#define MAX_LED_MGNT_PORT                2

/*! lport is mangment port or not */
#define IS_MGNT_PORT(lport)              (lport > (MAX_LED_UC_PORT - MAX_LED_MGNT_PORT))

/*! led bitstream base addr and width */
#define LED_SEND_DATA_WIDTH              2

/*! define LED custom data get */
#define LED_CONTROL_DATA_LANE_SPEED_GET(led_control_data)  ((led_control_data >> 1) & 0x7)

/*! The mapping table used to translate fornt port lane index to physical port number */
const uint16 dport_map[MAX_LED_UC_PORT]={1,2,3,4,5,6,7,8,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,9,10,11,12,13,14,15,16,33,34,35,36,37,38,39,40,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,41,42,43,44,45,46,47,48,65,66,67,68,69,70,71,72,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,73,74,75,76,77,78,79,80,97,98,99,100,101,102,103,104,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,105,106,107,108,109,110,111,112,129,130,131,132,133,134,135,136,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,137,138,139,140,141,142,143,144,161,162,163,164,165,166,167,168,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,169,170,171,172,173,174,175,176,193,194,195,196,197,198,199,200,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,201,202,203,204,205,206,207,208,225,226,227,228,229,230,231,232,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,256,233,234,235,236,237,238,239,240,257,258,259,260,261,262,263,264,273,274,275,276,277,278,279,280,281,282,283,284,285,286,287,288,265,266,267,268,269,270,271,272,289,290,291,292,293,294,295,296,305,306,307,308,309,310,311,312,313,314,315,316,317,318,319,320,297,298,299,300,301,302,303,304,321,322,323,324,325,326,327,328,337,338,339,340,341,342,343,344,345,346,347,348,349,350,351,352,329,330,331,332,333,334,335,336,353,354,355,356,357,358,359,360,369,370,371,372,373,374,375,376,377,378,379,380,381,382,383,384,361,362,363,364,365,366,367,368,385,386,387,388,389,390,391,392,401,402,403,404,405,406,407,408,409,410,411,412,413,414,415,416,393,394,395,396,397,398,399,400,417,418,419,420,421,422,423,424,433,434,435,436,437,438,439,440,441,442,443,444,445,446,447,448,425,426,427,428,429,430,431,432,449,450,451,452,453,454,455,456,465,466,467,468,469,470,471,472,473,474,475,476,477,478,479,480,457,458,459,460,461,462,463,464,481,482,483,484,485,486,487,488,497,498,499,500,501,502,503,504,505,506,507,508,509,510,511,512,489,490,491,492,493,494,495,496,516,515};

/*! buff used to save color if COMPRESS_MODE != 1 */
static uint8 colors[MAX_LED_UC_PORT];

/*!
 * \brief Function for LED bit pattern generator.
 *
 * Customer can compose the LED bit pattern to control serial LED
 * according to link/traffic information.
 *
 * \param [in,out] ctrl Data structure indicating the locations of the
 *                      port status and serial LED bit pattern RAM.
 * \param [in] cnt 30Hz counter.
 *
 */
void
customer_led_handler(soc_led_custom_handler_ctrl_t *ctrl, uint32 cnt)
{
    uint8 idx, color, new, lane_speed;
    uint16 accu_val;
    uint16 i, lport, led_uc_port, pos;

    for (lport = 1; lport <= MAX_LED_UC_PORT; lport ++) {
        /* led_uc_port = physical port number - constant. The constant is 1 for ESW chips */
        led_uc_port = dport_map[lport - 1] - 1;

        /* Read value from accumulation RAM */
        accu_val = LED_HW_RAM_READ16(ctrl->accu_ram_base, led_uc_port);

        color = LED_BIT_BLACK;

        if (accu_val & LED_HW_LINK) {
            if (IS_MGNT_PORT(lport)) {
                lane_speed = LED_CONTROL_DATA_LANE_SPEED_GET(ctrl->led_control_data[led_uc_port]);
                if (lane_speed != LANE_SPEED_25G) {
                    color = LED_BIT_AMBER;
                } else {
                    color = LED_BIT_GREEN;
                }
            }else{
                lane_speed = LED_CONTROL_DATA_LANE_SPEED_GET(ctrl->led_control_data[led_uc_port]);
                if (lane_speed != LANE_SPEED_100G) {
                    color = LED_BIT_AMBER;
                } else {
                    color = LED_BIT_GREEN;
                }
            }
        }

        if (IS_MGNT_PORT(lport)) {
            if ((accu_val & (LED_HW_RX | LED_HW_TX)) && (cnt & ACT_TICKS)) {
                color == LED_BIT_BLACK;
            }
            LED_HW_RAM_WRITE16(ctrl->pat_ram_base, lport, color);
        }else{
            if (accu_val & (LED_HW_RX | LED_HW_TX)) {
                if (color == LED_BIT_GREEN){
                    color = LED_BLINK_GREEN;
                }else{
                    color = LED_BLINK_AMBER;
                }
            }

            colors[lport - 1] = color;
        }
    }

    for (lport = 1, pos = 1; lport < (MAX_LED_UC_PORT - MAX_LED_MGNT_PORT); lport += COMPRESS_MODE, pos++) {
        for (i = 1, new = colors[lport - 1]; i < COMPRESS_MODE; i ++) {
            if (new != colors[lport - 1 + i]) {
                if (new == LED_BIT_BLACK) {
                    new = colors[lport - 1 + i];
                }else if (IS_BLINK_MODE(colors[lport - 1 + i])) {
                    new = colors[lport - 1 + i];
                }
            }
        }

        if (IS_BLINK_MODE(new)){
            if (cnt & ACT_TICKS){
                new = LED_BIT_BLACK;
            }else{
                new = GET_BLINK_COLOR(new);
            }
        }

        LED_HW_RAM_WRITE16(ctrl->pat_ram_base, pos, new);
    }

    /* Configure LED HW interfaces based on board configuration */
    for (idx = 0; idx < LED_HW_INTF_MAX_NUM; idx++) {
        soc_led_intf_ctrl_t *lic = &ctrl->intf_ctrl[idx];
        switch (idx) {
        case 0:

            /* Send the pattern over LED interface 0 for fornt LED 0 - 63 */
            lic->valid = 1;
            lic->start_row = 1;
            lic->end_row = 64;
            lic->pat_width = LED_SEND_DATA_WIDTH;
            break;
        case 1:

            /* Send the pattern over LED interface 1 for fornt LED 64 - 127 */
            lic->valid = 1;
            lic->start_row = 65;
            lic->end_row = 128;
            lic->pat_width = LED_SEND_DATA_WIDTH;
            break;
        case 2:

            /* Send the pattern over LED interface 2 for fornt sfp28 LED */
            lic->valid = 1;
            lic->start_row = 513;
            lic->end_row = 514;
            lic->pat_width = LED_SEND_DATA_WIDTH;
            break;
        default:

            /* Invalidate rest of the interfaces */
            lic->valid = 0;
            break;
        }
    }

    return;
}
