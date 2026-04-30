from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
import serial
import time

app = Flask(__name__)
app.secret_key = "REDES"

APP_USER = "admin"
# IMPORTANTE: Reemplaza este hash con el tuyo o usa la contraseña "admin" directamente
APP_PW_HASH = "scrypt:32768:8:1$fJBGT1vXjplpTKs4$31608a996a71fee1935865c481cb59268bde99dda64bcb59ef6c212affd6882cf0b01f2c66a554dfd12605031abc9a816fe783e0adb7c800f4bf0fec198b66c0"

# Configuración del puerto serial
arduino = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
time.sleep(2)

# Estado del motor
ultimo_estado = {
    "cmd": "P",
    "pulsos": 0,
    "vueltas": 0.0,
    "rpm": 0.0,
    "raw": "Esperando datos..."
}

# RPM de referencia (valor que el usuario puede cambiar)
rpm_referencia = 1000  # Valor por defecto

def is_logged_in():
    return session.get("logged_in", False)

def leer_serial():
    global ultimo_estado

    try:
        while arduino.in_waiting > 0:
            linea = arduino.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if linea:
                print("SERIAL:", linea)
                ultimo_estado["raw"] = linea

                try:
                    if "Cmd:" in linea:
                        cmd = linea.split("Cmd:")[1].split("Pulsos:")[0].strip()

                        pulsos = int(
                            linea.split("Pulsos:")[1]
                            .split("Vueltas:")[0]
                            .strip()
                        )

                        vueltas = float(
                            linea.split("Vueltas:")[1]
                            .split("RPM:")[0]
                            .strip()
                        )

                        rpm = float(
                            linea.split("RPM:")[1]
                            .split("A:")[0]
                            .strip()
                        )

                        ultimo_estado["cmd"] = cmd
                        ultimo_estado["pulsos"] = pulsos
                        ultimo_estado["vueltas"] = vueltas
                        ultimo_estado["rpm"] = rpm

                except Exception as e:
                    print("Error parseando:", e)

    except Exception as e:
        ultimo_estado["raw"] = f"Error serial: {str(e)}"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pw = request.form.get("password", "")

        if user == APP_USER and check_password_hash(APP_PW_HASH, pw):
            session["logged_in"] = True
            return redirect(url_for("index"))

        return render_template(
            "login.html",
            error="Usuario o contraseña incorrectos"
        )

    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    if not is_logged_in():
        return jsonify({"ok": False})

    leer_serial()
    
    # Calcular error
    global rpm_referencia
    rpm_actual = ultimo_estado["rpm"]
    error_abs = abs(rpm_actual - rpm_referencia)
    error_porcentual = (error_abs / rpm_referencia * 100) if rpm_referencia > 0 else 0
    
    # Determinar estado del semáforo
    if error_porcentual < 5:
        semaforo = "verde"
    elif error_porcentual < 15:
        semaforo = "amarillo"
    else:
        semaforo = "rojo"

    return jsonify({
        "ok": True,
        "cmd": ultimo_estado["cmd"],
        "pulsos": ultimo_estado["pulsos"],
        "vueltas": ultimo_estado["vueltas"],
        "rpm": rpm_actual,
        "raw": ultimo_estado["raw"],
        "rpm_referencia": rpm_referencia,
        "error_abs": round(error_abs, 2),
        "error_porcentual": round(error_porcentual, 2),
        "semaforo": semaforo
    })

@app.route("/api/referencia", methods=["POST"])
def set_referencia():
    """Endpoint para cambiar la RPM de referencia"""
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"})
    
    global rpm_referencia
    data = request.get_json()
    nueva_referencia = data.get("rpm_referencia", 1000)
    
    try:
        rpm_referencia = float(nueva_referencia)
        if rpm_referencia < 0:
            rpm_referencia = 0
        return jsonify({
            "ok": True,
            "rpm_referencia": rpm_referencia
        })
    except:
        return jsonify({"ok": False, "error": "Valor inválido"})

@app.route("/control", methods=["POST"])
def control():
    if not is_logged_in():
        return jsonify({
            "ok": False,
            "error": "No autorizado"
        })

    data = request.get_json()
    comando = data.get("comando", "")

    if comando in ["A", "R", "P", "Z"]:
        print("ENVIANDO:", comando)
        arduino.write((comando + "\n").encode())
        arduino.flush()

        return jsonify({
            "ok": True,
            "mensaje": f"Comando {comando} enviado correctamente"
        })

    return jsonify({
        "ok": False,
        "error": "Comando inválido"
    })

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
