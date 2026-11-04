from flask import Flask, render_template_string
import gpiod

app = Flask(__name__)
CHIP_PATH = "/dev/gpiochip0"
LINE_OFFSET = 6

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Banana Pi - Sterowanie LED</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background: #222; color: white; }
        .btn { padding: 15px 30px; font-size: 18px; margin: 10px; cursor: pointer; border: none; border-radius: 5px; }
        .on { background-color: #4CAF50; color: white; }
        .off { background-color: #f44336; color: white; }
    </style>
</head>
<body>
    <h1>Sterowanie diodą z poziomu WWW</h1>
    <a href="/on"><button class="btn on">Włącz LED</button></a>
    <a href="/off"><button class="btn off">Wyłącz LED</button></a>
</body>
</html>
"""

def set_led(state):
    with gpiod.request_lines(
        CHIP_PATH,
        consumer="Flask_LED",
        config={LINE_OFFSET: gpiod.LineSettings(direction=gpiod.line.Direction.OUTPUT)}
    ) as request:
        val = gpiod.line.Value.ACTIVE if state else gpiod.line.Value.INACTIVE
        request.set_value(LINE_OFFSET, val)

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/on")
def led_on():
    set_led(True)
    return render_template_string(HTML_TEMPLATE)

@app.route("/off")
def led_off():
    set_led(False)
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
