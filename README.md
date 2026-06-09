# Rescue - Control ROS 2

Proyecto ROS 2 para controlar el robot **Rescue** usando una Raspberry como nodo de motores y un PC como estación de control con mando PS4 e interfaz gráfica.

El sistema usa **ROS 2 Jazzy** y trabaja con el mismo `ROS_DOMAIN_ID` en la Raspberry y en el PC.

---

## Estructura general

```text
PC
├── joy_node              # Lee el control PS4
├── ps4_teleop_node       # Convierte el control PS4 en comandos de velocidad
└── dashboard_node        # Interfaz gráfica de monitoreo

Raspberry
└── motor_driver_node     # Recibe velocidades y controla los motores
```

---

## Comandos para encender todo

Ejecutar cada bloque en una terminal diferente.
Cada terminal debe quedar abierta mientras el robot está funcionando.

---

## 1. Raspberry - Nodo de motores

En la Raspberry, ejecutar:

```bash
cd ~/Rescue
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=10

ros2 run rescue_raspberry_brain motor_driver_node
```

Debe mostrar algo parecido a:

```text
Nodo Motor Driver iniciado.
Escuchando /cmd_vel...
Publicando /real_speed_abs...
```

Este nodo recibe comandos de velocidad desde `/cmd_vel`, controla los motores del robot y publica la velocidad real en `/real_speed_abs`.

---

## 2. PC - Nodo del control PS4

En el PC, ejecutar:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=10

ros2 run joy joy_node
```

Este nodo lee el control PS4 conectado al computador y publica los datos del mando en el tópico `/joy`.

---

## 3. PC - Nodo principal de teleoperación

En otra terminal del PC, ejecutar:

```bash
cd ~/Rescue
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=10

ros2 run rescue_pc_brain ps4_teleop_node
```

Este nodo toma la información del control PS4 desde `/joy` y la convierte en comandos de movimiento para el robot.

Publica los comandos en:

```text
/cmd_vel
```

---

## 4. PC - Interfaz gráfica

En otra terminal del PC, ejecutar:

```bash
cd ~/Rescue
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=10

ros2 run rescue_pc_brain dashboard_node
```

Este nodo abre la interfaz gráfica del sistema.

La ventana muestra información como:

```text
Caja
Dirección
Estado
Velocidad deseada
```

Sirve para monitorear el comportamiento del robot mientras se controla con el mando PS4.

---

## Nodos principales

### `motor_driver_node`

Se ejecuta en la Raspberry.

Función:

* Escucha comandos de velocidad en `/cmd_vel`.
* Controla el driver de motores.
* Publica la velocidad real del robot en `/real_speed_abs`.

---

### `joy_node`

Se ejecuta en el PC.

Función:

* Lee el control PS4.
* Publica los botones y ejes del mando en `/joy`.

---

### `ps4_teleop_node`

Se ejecuta en el PC.

Función:

* Recibe los datos del control PS4 desde `/joy`.
* Interpreta los botones y joysticks.
* Genera comandos de velocidad para mover el robot.
* Publica en `/cmd_vel`.

---

### `dashboard_node`

Se ejecuta en el PC.

Función:

* Abre la interfaz gráfica.
* Muestra el estado del robot.
* Permite visualizar información de control y velocidad.

---

## Notas importantes

Todos los equipos deben usar el mismo dominio ROS:

```bash
export ROS_DOMAIN_ID=10
```

La Raspberry y el PC deben estar conectados a la misma red.

Antes de ejecutar los nodos propios del proyecto, siempre cargar el entorno:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

---

## Orden recomendado de ejecución

1. Encender la Raspberry.
2. Ejecutar `motor_driver_node`.
3. Conectar el control PS4 al PC.
4. Ejecutar `joy_node`.
5. Ejecutar `ps4_teleop_node`.
6. Ejecutar `dashboard_node`.
7. Probar movimiento del robot desde el control.

---

## Verificación rápida

Para revisar que los tópicos estén activos:

```bash
ros2 topic list
```

Se deberían ver tópicos como:

```text
/joy
/cmd_vel
/real_speed_abs
```

Para revisar los datos del control:

```bash
ros2 topic echo /joy
```

Para revisar los comandos enviados al robot:

```bash
ros2 topic echo /cmd_vel
```
