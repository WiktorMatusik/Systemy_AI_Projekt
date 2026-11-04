import time
import gpiod

CHIP_PATH = "/dev/gpiochip0"
LINE_OFFSET = 6

try:
    with gpiod.request_lines(
        CHIP_PATH,
        consumer="LED_Blink",
        config={
            LINE_OFFSET: gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=gpiod.line.Value.INACTIVE
            )
        }
    ) as request:
        print("Rozpoczynam miganie diodą (Naciśnij Ctrl+C, aby zatrzymać)...")
        while True:
            request.set_value(LINE_OFFSET, gpiod.line.Value.ACTIVE)
            time.sleep(1)
            request.set_value(LINE_OFFSET, gpiod.line.Value.INACTIVE)
            time.sleep(1)

except KeyboardInterrupt:
    print("\nProgram zatrzymany przez użytkownika. Dioda zgaszona.")
