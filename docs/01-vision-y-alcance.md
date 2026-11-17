# 1. Visión y alcance

> Estado del documento: **actualizado en la fase de rediseño de interfaz y limpieza (2026-11-16)**.
> Describe el proyecto tal como es hoy. La historia (de PaaS a monitorización) está resumida en el
> apartado 1.6 y archivada en [historico/](historico/README.md).

## 1.1 Problema

Un servidor doméstico con Docker ejecuta servicios que se crean de formas distintas (`docker run`,
Compose, otras herramientas). Para saber si el servidor está sano hay que entrar por terminal y usar
varios comandos (`top`, `free`, `df`, `docker ps`...). No hay una vista única y sencilla con el
estado del servidor y de todos sus contenedores.

## 1.2 Objetivo

Construir **Server Monitoring Service**: una plataforma web ligera de **monitorización y consulta**
que muestra, tras iniciar sesión:

1. **Métricas del servidor anfitrión:** CPU, RAM, uno o varios discos, temperatura general (paquete del
   procesador), red (velocidad de bajada y subida), sistema operativo, kernel, *hostname* y tiempo en
   marcha, con indicadores y gráficas de la evolución de los últimos 10 minutos.
2. **Todos los contenedores Docker, en ejecución y detenidos:** nombre, imagen, estado, salud, puertos,
   fecha de creación y proyecto/servicio de Docker Compose, **incluidos los creados fuera de la
   plataforma**.

La plataforma es **solo de lectura**: no crea, inicia, para, borra ni modifica contenedores, imágenes
ni volúmenes. Debe ser **funcional, sencilla y segura**, y su código debe poder ser comprendido,
explicado y demostrado por el equipo.

## 1.3 Alcance

### Dentro del alcance

| Área | Incluido |
|---|---|
| Acceso | Inicio de sesión con una contraseña única, cierre de sesión, caducidad de sesión |
| Métricas del anfitrión | CPU (%, núcleos, modelo), RAM, disco raíz y discos extra declarados por el administrador, temperatura general, red, SO, kernel, arquitectura, *hostname*, uptime |
| Contenedores | Lista de **todos**: nombre, imagen, estado, salud, puertos, creación, proyecto y servicio de Compose |
| Gráficas | Evolución de CPU, RAM y red de los últimos 10 minutos, en el navegador |
| Actualización | Consulta automática cada 5 s, con pausa si la pestaña no está visible |
| Seguridad | Agente de solo lectura aislado, token, Argon2id, límite de intentos, CSRF, CSP |

### Fuera del alcance (decisión consciente)

| Excluido | Motivo |
|---|---|
| Crear, iniciar, parar, reiniciar o borrar contenedores, imágenes y volúmenes | Es el núcleo del cambio de objetivo: solo lectura (ADR-036) |
| Desplegar aplicaciones, plantillas, revisiones, *rollback* | Eran el objetivo PaaS |
| Historial de métricas en el servidor | El histórico vive en el navegador y empieza de cero al recargar (ADR-047) |
| Consumo por contenedor, logs, alertas y notificaciones | No pedido |
| Varios usuarios y roles | Una única contraseña |
| Multi-nodo, Kubernetes | Un solo servidor |
| HTTPS propio | Se podrá poner delante un proxy; `SMS_COOKIE_SECURE=true` ya está disponible |
| Tema claro | Solo hay tema oscuro |

### Criterio de éxito

Una plataforma que funcione, sea estable y segura dentro de su alcance, ejecutable en el servidor
doméstico, con interfaz clara, arquitectura coherente, código legible y documentación suficiente para
defenderla académicamente.

## 1.4 Restricciones

- **No poner en riesgo el servidor real.** Todo el desarrollo y las pruebas se hacen en local. A fecha
  de este documento **no** se ha probado en el servidor Ubuntu real.
- **Solo lectura**, también en el código: el agente únicamente consulta (ADR-037).
- **Recursos limitados.** Objetivo de diseño de bajo consumo (RNF-M11), todavía sin medir.
- **Tecnologías comprensibles.** Cada pieza debe poder explicarse en la defensa. Sin librerías de
  JavaScript, sin base de datos, sin dependencias nuevas de Python respecto a la Fase 2.
- **Proyecto académico de duración limitada.** Se prioriza un núcleo pequeño y sólido.

## 1.5 Usuarios

| Rol | Descripción |
|---|---|
| Administrador | Persona que consulta el estado del servidor. Es el **único usuario**: comparte una contraseña única. |

## 1.6 Evolución del proyecto

El proyecto nació como una **PaaS ligera** (MiniPaaS) para desplegar y administrar aplicaciones en
contenedores. Las Fases 0 a 2 (2026-11-15) construyeron su base; la Fase 3 (motor de despliegue)
quedó sin aprobar en la rama `fase-03-motor-despliegue`. El 2026-11-16 la **renovación** cambió el
objetivo a monitorización de solo lectura (ADR-036) por ser más sencillo, seguro y defendible, y la
fase de **rediseño de interfaz y limpieza** (misma fecha) renombró el proyecto a Server Monitoring
Service, amplió el backend (discos, temperatura, red, contenedores detenidos), rediseñó la interfaz y
limpió el código. La documentación de la etapa PaaS se conserva en
[historico/](historico/README.md); los informes de cada etapa, en
[informes/renovacion-monitorizacion.md](informes/renovacion-monitorizacion.md) y
[informes/rediseno-interfaz-limpieza.md](informes/rediseno-interfaz-limpieza.md).

## 1.7 Situación actual y siguientes pasos

| Etapa | Estado |
|---|---|
| Fases 0 a 2 (PaaS) | Aprobadas; se conservan como etapa anterior |
| Fase 3 (motor de despliegue) | Rama `fase-03-motor-despliegue`, **no aprobada**, intacta |
| Renovación: plataforma de monitorización | Terminada (informe en `informes/`) |
| **Rediseño de interfaz y limpieza** | **Terminada en local, pendiente de aprobación** (rama `rediseno-interfaz-limpieza`) |

Siguientes pasos recomendados (propuestos, no aprobados):

| Paso | Contenido | Criterio de aceptación |
|---|---|---|
| **A. Cierre de pendientes de la fase actual** | Ejecutar `verify_dev_env.sh` con el entorno renombrado y construir desde un entorno limpio siguiendo la guía; comprobar la ventana de 10 minutos llena en el navegador | Resultados anotados en [07-pruebas.md](07-pruebas.md) |
| **B. Despliegue en el servidor Ubuntu real** (solo con autorización expresa) | Probar antes en Ubuntu o una VM; decidir HTTPS y `SMS_COOKIE_SECURE`; guía de instalación; medir consumo | Funciona sin afectar a los servicios existentes; consumo medido |
| **C. Cierre académico** | Memoria, presentación y cuestionario de la asignatura | Documentación completa |

Posibles mejoras posteriores, no planificadas: proxy del socket de Docker que solo permita lecturas,
tema claro, tooltip accesible por teclado, historial de métricas persistente, sesiones compartidas
entre procesos. Cualquier cambio de alcance requiere aprobación del usuario.
