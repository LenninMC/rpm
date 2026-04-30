// ============================================
// CONTROL DE MOTOR DC CON ENCODER
// ============================================

// Pines para el puente H (L298N)
const int pinIN1 = 7;
const int pinIN2 = 8;
const int pinEN  = 9;

// Pines para el encoder
const int pinA = 2;
const int pinB = 3;

// Variables para encoder
volatile long contador = 0;
volatile uint8_t estadoAnterior = 0;

long conteoAnterior = 0;
unsigned long tiempoAnterior = 0;

float rpm = 0.0;
char comando = 'P';

// AJUSTA ESTE VALOR SEGUN TU ENCODER REAL
const float CPR = 3200.0;  // Pulsos por revolución

// Velocidades PWM (0-255)
const int VELOCIDAD_MOTOR = 180;

// Tabla de cuadratura
const int8_t tabla[16] = {
   0, -1,  1,  0,
   1,  0,  0, -1,
  -1,  0,  0,  1,
   0,  1, -1,  0
};

inline uint8_t leerEncoder() {
  uint8_t a = digitalRead(pinA);
  uint8_t b = digitalRead(pinB);
  return (a << 1) | b;
}

void encoderISR() {
  uint8_t estadoActual = leerEncoder();
  uint8_t indice = (estadoAnterior << 2) | estadoActual;
  contador += tabla[indice];
  estadoAnterior = estadoActual;
}

void motorAdelante() {
  digitalWrite(pinIN1, HIGH);
  digitalWrite(pinIN2, LOW);
  analogWrite(pinEN, VELOCIDAD_MOTOR);
}

void motorAtras() {
  digitalWrite(pinIN1, LOW);
  digitalWrite(pinIN2, HIGH);
  analogWrite(pinEN, VELOCIDAD_MOTOR);
}

void motorParo() {
  analogWrite(pinEN, 0);
  digitalWrite(pinIN1, LOW);
  digitalWrite(pinIN2, LOW);
}

void leerSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == 'A' || c == 'a') {
      comando = 'A';
      Serial.println("OK:ADELANTE");
    }
    else if (c == 'R' || c == 'r') {
      comando = 'R';
      Serial.println("OK:ATRAS");
    }
    else if (c == 'P' || c == 'p') {
      comando = 'P';
      Serial.println("OK:PARO");
    }
    else if (c == 'Z' || c == 'z') {
      noInterrupts();
      contador = 0;
      conteoAnterior = 0;
      interrupts();
      Serial.println("OK:RESET");
    }
  }
}

void calcularRPM() {
  unsigned long ahora = millis();

  if (ahora - tiempoAnterior >= 100) {
    long cuentaActual;

    noInterrupts();
    cuentaActual = contador;
    interrupts();

    long delta = cuentaActual - conteoAnterior;
    rpm = (delta * 60.0) / (CPR * 0.1);

    conteoAnterior = cuentaActual;
    tiempoAnterior = ahora;
  }
}

void enviarDatos() {
  static unsigned long lastSend = 0;
  unsigned long ahora = millis();

  if (ahora - lastSend >= 200) {
    lastSend = ahora;

    long c;
    noInterrupts();
    c = contador;
    interrupts();

    float vueltas = (float)c / CPR;
    String estadoMotor = "";
    
    if (comando == 'A') estadoMotor = "ADELANTE";
    else if (comando == 'R') estadoMotor = "ATRAS";
    else estadoMotor = "PARADO";

    // Formato para el servidor: Cmd: A  Pulsos: 1234  Vueltas: 0.3856  RPM: 1250.50  A:1  B:0
    Serial.print("Cmd: ");
    Serial.print(comando);
    Serial.print("  Pulsos: ");
    Serial.print(c);
    Serial.print("  Vueltas: ");
    Serial.print(vueltas, 4);
    Serial.print("  RPM: ");
    Serial.print(rpm, 2);
    Serial.print("  A:");
    Serial.print(digitalRead(pinA));
    Serial.print("  B:");
    Serial.println(digitalRead(pinB));
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(pinIN1, OUTPUT);
  pinMode(pinIN2, OUTPUT);
  pinMode(pinEN, OUTPUT);

  pinMode(pinA, INPUT_PULLUP);
  pinMode(pinB, INPUT_PULLUP);

  motorParo();
  delay(500);

  estadoAnterior = leerEncoder();
  tiempoAnterior = millis();

  attachInterrupt(digitalPinToInterrupt(pinA), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(pinB), encoderISR, CHANGE);

  Serial.println("=== SISTEMA DE CONTROL CON ENCODER ===");
  Serial.println("Comandos: A=Adelante R=Atras P=Paro Z=Reset");
  Serial.println("=======================================");
}

void loop() {
  leerSerial();

  switch (comando) {
    case 'A':
      motorAdelante();
      break;
    case 'R':
      motorAtras();
      break;
    default:
      motorParo();
      break;
  }

  calcularRPM();
  enviarDatos();
}
