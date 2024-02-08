#include <linux/module.h>
#include <linux/jiffies.h>
#include <linux/i2c.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/err.h>
#include <linux/delay.h>
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include <linux/slab.h>
#include <linux/dmi.h>
#include "../../../../pddf/i2c/modules/include/pddf_psu_defs.h"

ssize_t pddf_show_custom_fan_dir(struct device *dev, struct device_attribute *da, char *buf);
extern PSU_SYSFS_ATTR_DATA access_psu_fan_dir;

ssize_t pddf_show_custom_fan_dir(struct device *dev, struct device_attribute *da, char *buf)
{
    return sprintf(buf, "FAN_DIRECTION_INTAKE\n");
}

static int __init pddf_psu_patch_init(void)
{
    access_psu_fan_dir.show = pddf_show_custom_fan_dir;
    access_psu_fan_dir.do_get = NULL;
    return 0;
}

static void __exit pddf_psu_patch_exit(void)
{
    return;
}

MODULE_AUTHOR("Fan Xinghua");
MODULE_DESCRIPTION("pddf custom psu api");
MODULE_LICENSE("GPL");

module_init(pddf_psu_patch_init);
module_exit(pddf_psu_patch_exit);
