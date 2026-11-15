# 1. Visión y alcance

> Estado del documento: **propuesta de la Fase 0**, pendiente de aprobación.

## 1.1 Problema

Un servidor doméstico con Docker permite ejecutar aplicaciones, pero gestionarlas exige conocer
comandos (`docker run`, `docker compose`, redes, volúmenes, límites…) y recordar cómo se desplegó
cada una. No existe una visión centralizada del estado de las aplicaciones ni un historial de
despliegues, y un error manual puede afectar a servicios que ya están funcionando.

## 1.2 Objetivo

Diseñar e implementar **MiniPaaS**, una plataforma como servicio (PaaS) ligera y autohospedada que:

- ofrezca un **panel web** desde el que desplegar y administrar aplicaciones sin usar la terminal;
- trabaje con el concepto de **aplicación y despliegue**, no con contenedores sueltos;
- use **Docker Engine** como runtime subyacente, ocultando sus detalles al usuario;
- sea **segura por diseño**: el componente con privilegios está aislado y solo acepta operaciones
  permitidas;
- funcione en un **servidor doméstico con recursos limitados** sin interferir con los servicios
  existentes.

Título provisional del trabajo: *«Diseño e implementación de una plataforma PaaS ligera para el
despliegue y gestión de aplicaciones distribuidas»*.

## 1.3 Qué es «aplicación» en MiniPaaS

Una **aplicación** es una unidad lógica con nombre que el usuario gestiona como un todo. Está
formada por uno o varios **servicios** (por ejemplo, `web` + `redis`). Cada servicio se ejecuta como
un contenedor creado a partir de una imagen. Los servicios de una misma aplicación se comunican
por una **red privada propia** de la aplicación, resolviéndose por nombre; las aplicaciones están
aisladas entre sí. Esto es lo que justifica el término *aplicaciones distribuidas* del título.

Un **despliegue** es una versión concreta de la configuración de la aplicación (imágenes, variables,
puertos, volúmenes, límites). Cada cambio genera un nuevo despliegue numerado, lo que permite
consultar el historial y volver a una versión anterior.

## 1.4 Alcance

### Dentro del alcance (objetivo del proyecto)

| Área | Incluido |
|---|---|
| Aplicaciones | Crear, listar, consultar, editar, eliminar |
| Despliegue | Desde imagen de un registro público y desde plantillas propias predefinidas |
| Ciclo de vida | Iniciar, detener, reiniciar, redesplegar, volver a un despliegue anterior |
| Configuración | Variables de entorno (con valores secretos ocultos en la interfaz), puertos |
| Almacenamiento | Volúmenes persistentes con nombre, que sobreviven a los redespliegues |
| Redes | Red privada por aplicación; exposición controlada de puertos al exterior |
| Recursos | Límites de CPU y memoria por servicio; política de reinicio |
| Monitorización | Estado, salud (health checks), consumo de CPU/memoria, logs, métricas del host |
| Seguridad | Autenticación, validación de entradas, agente privilegiado aislado, registro de auditoría |
| Interfaz | Panel web sencillo, coherente y comprensible para alguien que no conoce Docker |

### Fuera del alcance (decisión consciente)

| Excluido | Motivo |
|---|---|
| Construir imágenes desde código fuente o Git (*buildpacks*) | Coste de CPU/disco alto en el servidor y superficie de ataque amplia. Posible extensión opcional. |
| Ficheros `docker-compose.yml` arbitrarios subidos por el usuario | Permitirían `privileged`, montajes del host, etc. Se usan plantillas propias validadas. |
| Multi-nodo, clúster, planificación entre máquinas | Hardware de un solo servidor. Se discute como limitación y trabajo futuro. |
| Autoescalado horizontal | Sin varios nodos no aporta valor real; se puede discutir conceptualmente. |
| Multi-inquilino con aislamiento fuerte entre usuarios | Un servidor doméstico tiene uno o pocos administradores. |
| Kubernetes, OpenStack, Proxmox | Peso excesivo para el hardware y el alcance (ver `decisiones.md`, ADR-001). |
| Certificados TLS públicos automáticos | Depende de un dominio público; se valorará en la fase de despliegue final. |

### Criterio de éxito

Ver el apartado 15 del enunciado del proyecto: una plataforma que funcione, estable y segura dentro
de su alcance, ejecutable en el servidor doméstico, con interfaz sencilla, arquitectura coherente,
código legible y documentación suficiente para defenderla académicamente.

## 1.5 Restricciones

- **No poner en riesgo el servidor real.** Todo el desarrollo y las pruebas se hacen en local. La
  plataforma solo puede actuar sobre recursos Docker que ella misma ha creado (marcados con la
  etiqueta `minipaas.managed=true`).
- **Recursos limitados.** Objetivo: los componentes propios de MiniPaaS deben consumir menos de
  ~250 MB de RAM en reposo.
- **Tecnologías comprensibles.** Cada pieza debe poder explicarse en la defensa.
- **Proyecto académico de duración limitada.** Se prioriza un núcleo sólido frente a muchas
  funcionalidades a medias.

## 1.6 Usuarios

| Rol | Descripción |
|---|---|
| Administrador | Persona que gestiona el servidor y despliega aplicaciones. Usuario principal. |
| Visitante de una aplicación | Accede a la aplicación desplegada (no al panel). No interactúa con MiniPaaS. |

La existencia de un rol adicional de solo lectura está pendiente de decisión (ver `decisiones.md`).
