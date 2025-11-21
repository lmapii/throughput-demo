
#include <stdlib.h>

#include <zephyr/drivers/gpio.h>
#include <zephyr/input/input.h>
#include <zephyr/kernel.h>
#include <zephyr/shell/shell.h>

#include <zephyr/logging/log.h>
LOG_MODULE_DECLARE(app, LOG_LEVEL_DBG);

/*******************************************************************************
 * Definitions
 ******************************************************************************/

#define DT_PROP_OR_EMPTY(node_id, prop) \
    COND_CODE_1(DT_NODE_HAS_PROP(node_id, prop), (DT_PROP(node_id, prop), ), ())

static void prv_handle_button(int32_t const value);

static void prv_input_cb_buttons(struct input_event *evt, void *user_data);

static int prv_shell_simulate_button(
    const struct shell *sh, size_t argc, char **argv);

/*******************************************************************************
 * Data
 ******************************************************************************/

static struct device const *const buttons_dev = DEVICE_DT_GET(
    DT_NODELABEL(buttons));

static struct gpio_dt_spec const led0 = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);

// clang-format off
static uint16_t const button_codes[] = {
    DT_PROP_OR_EMPTY(DT_NODELABEL(button0), zephyr_code)
    DT_PROP_OR_EMPTY(DT_NODELABEL(button1), zephyr_code)
};
// clang-format on

static bool light_is_on = false;

// to use the input shell, e.g., `input report 1 11 1`, the
// device has to be NULL since the input shell doesn't allow reporting
// for a specific device
INPUT_CALLBACK_DEFINE(NULL, prv_input_cb_buttons, NULL);

/*******************************************************************************
 * Functions
 ******************************************************************************/

static void prv_handle_button(int32_t const value)
{
    // the event's value is > 0 if the button is being pressed.
    // toggle the light on button press, don't do anything on release.
    if (value > 0)
    {
        light_is_on = !light_is_on;
        int ret     = gpio_pin_set_dt(&led0, light_is_on ? 1 : 0);
        __ASSERT_NO_MSG(ret >= 0);
    }
}

static void prv_input_cb_buttons(struct input_event *evt, void *user_data)
{
    __ASSERT_NO_MSG(evt != NULL);
    (void) user_data;

    LOG_DBG(
        "input device '%s', zephyr_code=%u, value=%d\n",
        evt->dev->name,
        evt->code,
        evt->value);

    for (size_t i = 0U; i < ARRAY_SIZE(button_codes); i++)
    {
        if (evt->code == button_codes[i])
        {
            prv_handle_button(evt->value);
        }
    }
}

int main(void)
{
    (void) buttons_dev;

    bool ready = gpio_is_ready_dt(&led0);
    __ASSERT_NO_MSG(ready);

    int ret = gpio_pin_configure_dt(&led0, GPIO_OUTPUT_ACTIVE);
    __ASSERT_NO_MSG(ret >= 0);

    ret = gpio_pin_set_dt(&led0, 0);
    __ASSERT_NO_MSG(ret >= 0);

    while (1)
    {
        k_msleep(1000U);
    }
}

static int prv_shell_simulate_button(
    const struct shell *sh, size_t argc, char **argv)
{
    (void) argc;
    char *end_ptr;

    // strtoul also parses hexadecimal numbers
    const unsigned long arg_value = strtoul(argv[1], &end_ptr, 0);
    if (*end_ptr != '\0')
    {
        shell_error(sh, "invalid parameter '%s' for value", argv[1]);
        return -EINVAL;
    }

    if (arg_value > UINT32_MAX)
    {
        shell_error(
            sh,
            "value %lu is out of its allowed range [0x0, 0x%lx]",
            arg_value,
            UINT32_MAX);
        return -EINVAL;
    }

    shell_print(sh, "simulating button value %lu", arg_value);
    prv_handle_button(arg_value);
    return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(
    sub_cmd,
    SHELL_CMD_ARG(
        simulate_button,
        NULL,
        "simulate button value",
        prv_shell_simulate_button,
        2,
        0),
    SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(
    demo, &sub_cmd, "demo for an application command with sub commands", NULL);
