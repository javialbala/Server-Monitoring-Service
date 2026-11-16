# 7. Fundamentos y estado del arte

> Estado del documento: **primera versión (Fase 0)**. Las afirmaciones marcadas con *(verificar)*
> deben contrastarse con la fuente primaria antes de pasar a la memoria final. El apartado 7.6 se
> añadió en la renovación (2026-11-16); los apartados 7.1 a 7.5 describen la etapa PaaS original y se
> conservan como contexto teórico.

## 7.1 Definición de cloud computing (NIST SP 800-145)

El NIST define el cloud computing como un modelo que permite el acceso ubicuo, cómodo y bajo
demanda, a través de la red, a un conjunto compartido de recursos de computación configurables
(redes, servidores, almacenamiento, aplicaciones y servicios) que pueden aprovisionarse y liberarse
rápidamente con un esfuerzo de gestión o una interacción con el proveedor mínimos
[NIST SP 800-145, Mell y Grance, 2011].

El modelo se compone de **cinco características esenciales**, **tres modelos de servicio** y **cuatro
modelos de despliegue**.

### Características esenciales y cómo se reflejan en MiniPaaS

| Característica (NIST) | En MiniPaaS |
|---|---|
| Autoservicio bajo demanda | El administrador despliega aplicaciones desde el panel sin intervención manual sobre Docker. |
| Amplio acceso por red | Panel y API accesibles por HTTP desde la red. |
| Agrupación de recursos (*resource pooling*) | CPU, memoria y disco del servidor se comparten entre aplicaciones aisladas. |
| Elasticidad rápida | **Parcial**: se pueden cambiar límites y redesplegar, pero no hay escalado automático (un solo nodo). Es una limitación a discutir. |
| Servicio medido | Monitorización de consumo de CPU, memoria y disco por aplicación. |

### Modelos de servicio

| Modelo | El consumidor gestiona | El proveedor gestiona | Ejemplos |
|---|---|---|---|
| **IaaS** | SO, runtime, aplicación, datos | Hardware, red, virtualización | Amazon EC2, OpenStack |
| **PaaS** | Aplicación y datos (y su configuración) | Todo lo anterior + SO + runtime + despliegue | Heroku, Cloud Foundry, OpenShift, Google App Engine |
| **SaaS** | Solo uso y configuración de usuario | Todo | Gmail, Microsoft 365 |

**MiniPaaS es una PaaS** porque el usuario aporta la aplicación (como imagen de contenedor) y su
configuración, y la plataforma se encarga del runtime, la red, el almacenamiento, el ciclo de vida y
la monitorización. Se diferencia de las PaaS clásicas basadas en *buildpacks* en que la unidad de
despliegue es una imagen ya construida, de forma similar a las plataformas «Container as a Service».
Esta frontera PaaS/CaaS debe discutirse en la memoria.

### Modelos de despliegue

Nube privada, comunitaria, pública e híbrida. **MiniPaaS es una nube privada** de un único
propietario, desplegada en sus instalaciones.

## 7.2 Contenedores y Docker

- **Contenedor**: proceso aislado del resto del sistema mediante mecanismos del kernel Linux:
  *namespaces* (PID, red, montajes, usuarios…), *cgroups* (límites de CPU/memoria) y capacidades.
  Comparte el kernel con el host, a diferencia de una máquina virtual.
- **Imagen**: plantilla inmutable por capas a partir de la cual se crean contenedores.
- **Docker Engine**: demonio (`dockerd`) que gestiona imágenes, contenedores, redes y volúmenes y
  expone una API REST a través de un socket Unix (`/var/run/docker.sock`).
- **Docker Compose**: herramienta para definir y ejecutar aplicaciones multi-contenedor mediante un
  fichero YAML.
- **Redes *bridge* definidas por el usuario**: proporcionan aislamiento entre grupos de contenedores
  y resolución DNS por nombre de contenedor/servicio. MiniPaaS crea una por aplicación.
- **Volúmenes con nombre**: almacenamiento persistente gestionado por Docker, independiente del ciclo
  de vida de los contenedores.

Implicación clave: el acceso al socket de Docker equivale a privilegios de root en el host, lo que
motiva el agente aislado de MiniPaaS (ADR-002).

## 7.3 Plataformas de referencia

### Red Hat OpenShift

- Plataforma de aplicaciones empresarial de Red Hat construida sobre **Kubernetes** (desde la
  versión 3). OKD es su distribución comunitaria.
- Conceptos relevantes: *projects* (espacios de nombres con control de acceso), *routes* para exponer
  servicios mediante un router/proxy, *Source-to-Image* (S2I) para construir imágenes desde código,
  *ImageStreams*, despliegues con estrategias *rolling* y *recreate*, consola web y CLI `oc`.
- Lo que tomamos como referencia: separación por proyecto (≈ red privada por aplicación), estrategia
  *recreate*, historial de despliegues, consola web orientada a aplicaciones.
- Por qué no lo usamos: requiere un clúster Kubernetes y recursos muy superiores a los de un
  servidor doméstico; incluso la variante de nodo único exige del orden de 8 vCPU y 16 GB de RAM
  *(verificar en la documentación oficial vigente)*.

### Cloud Foundry

- PaaS de código abierto iniciada en VMware (2011) y gobernada por la **Cloud Foundry Foundation**
  (Linux Foundation).
- Flujo característico: `cf push` sube el código, un *buildpack* lo convierte en un *droplet* y la
  plataforma lo ejecuta en contenedores, gestionando rutas, escalado e instancias.
- Componentes: planificador **Diego**, contenedores **Garden**, router **Gorouter**, autenticación
  **UAA**, despliegue de la propia plataforma con **BOSH**, servicios mediante *service brokers*
  (Open Service Broker API).
- Lo que tomamos como referencia: experiencia «aplicación primero», configuración por variables de
  entorno, enlace de servicios, separación entre plataforma y aplicación.
- Por qué no lo usamos: despliegue complejo (BOSH) y consumo de recursos elevado para un único
  servidor doméstico.

### HPE Helion Stackato (referencia histórica)

- **Stackato** fue una PaaS privada basada en Cloud Foundry lanzada por **ActiveState** en 2012.
- HP la utilizó como base de su *Helion Development Platform* (2014) y **adquirió el negocio de
  Stackato en julio de 2015**, integrándolo en la familia HPE Helion.
- HPE desinvirtió posteriormente en esta línea de producto *(verificar fecha y destino exactos)*.
- Interés para el trabajo: muestra la evolución de las PaaS privadas «empaquetadas» basadas en
  Cloud Foundry y cómo muchas acabaron sustituidas por plataformas sobre Kubernetes.

### PaaS ligeras autohospedadas (las más cercanas a MiniPaaS)

| Plataforma | Idea | Relación con MiniPaaS |
|---|---|---|
| **Heroku** (comercial) | PaaS pionera; origen de la metodología *The Twelve-Factor App* | Inspiración conceptual (configuración por entorno, procesos sin estado, logs como flujos). |
| **Dokku** | «Mini-Heroku» sobre Docker con `git push` y buildpacks | Mismo nicho (un servidor), pero orientado a CLI y a construir desde código. |
| **CapRover** | PaaS con panel web sobre Docker Swarm y Nginx | Muy próximo en objetivos; usa Swarm y da acceso amplio a Docker. |
| **Coolify** | PaaS autohospedada moderna con panel web | Muy próxima; mucho más amplia y compleja. |
| **Portainer** | Interfaz de gestión de Docker/Kubernetes | No es una PaaS: gestiona contenedores, no aplicaciones con despliegues versionados. |

**Aportación de MiniPaaS frente a ellas:** no pretende competir en funcionalidad, sino ser una
implementación **pequeña, comprensible y con un diseño de seguridad explícito** (agente con lista
blanca y protección de los recursos ajenos), adecuada para estudiar cómo funciona una PaaS por dentro.

## 7.4 Comparación resumida

| Criterio | OpenShift | Cloud Foundry | Dokku / CapRover | MiniPaaS |
|---|---|---|---|---|
| Base | Kubernetes | Diego/Garden (o Kubernetes con Korifi) | Docker (+ Swarm en CapRover) | Docker Engine |
| Unidad de despliegue | Imagen o código (S2I) | Código (buildpack) o imagen | Código o imagen | Imagen o plantilla |
| Multi-nodo | Sí | Sí | Limitado | No |
| Recursos mínimos | Muy altos | Altos | Bajos | Muy bajos (objetivo < 250 MB) |
| Complejidad de operación | Alta | Alta | Baja-media | Baja |
| Objetivo | Producción empresarial | Producción empresarial | Uso personal/pequeños equipos | Académico + uso doméstico |

## 7.5 Conceptos de GSASD aplicados

| Concepto | Dónde aparece |
|---|---|
| Modelos de servicio cloud (IaaS/PaaS/SaaS) | Posicionamiento de MiniPaaS como PaaS de nube privada. |
| Servicios distribuidos | Aplicaciones multi-servicio comunicadas por red y DNS; control plane y agente comunicados por API. |
| Sistemas de archivos y almacenamiento persistente | Volúmenes con nombre, separación datos/cómputo, copias de seguridad de volúmenes. |
| Redes y comunicaciones | Redes *bridge* aisladas, DNS interno, publicación de puertos, proxy inverso, red interna del plano de control. |
| Virtualización ligera y aislamiento | Namespaces, cgroups, capacidades, comparación con máquinas virtuales. |
| Gestión de recursos | Límites de CPU/memoria con cgroups, cuotas. |
| Monitorización y observabilidad | Métricas, logs, health checks, estado deseado frente a estado real. |
| Seguridad | Mínimo privilegio, defensa en profundidad, modelo de amenazas, autenticación. |
| Tolerancia a fallos | Restauración automática de despliegues fallidos, políticas de reinicio, reconciliación. |

## 7.6 Herramientas de monitorización comparables (renovación)

Con el cambio de objetivo (ADR-036) el proyecto pasa a ser una herramienta de **monitorización de
solo lectura**. Estas son las alternativas conocidas con las que se compara. La descripción es
general y no se aportan cifras de consumo ni rendimiento, porque no se han medido.

| Herramienta | Idea | Diferencia con este proyecto |
|---|---|---|
| **Netdata** | Agente de monitorización en tiempo real con muchísimas métricas, gráficas e historial | Mucho más completo y complejo; este proyecto muestra solo el estado actual con pocas métricas |
| **Glances** | Monitor del sistema escrito en Python, con interfaz de terminal y modo web | Similar en espíritu; no está pensado para separar el proceso expuesto del acceso a Docker ni para tener inicio de sesión propio |
| **cAdvisor** | Recoge el uso de recursos de los contenedores (de Google) | Se centra en métricas por contenedor; aquí solo se listan los contenedores y el estado del anfitrión |
| **Prometheus + node_exporter** | `node_exporter` expone métricas del anfitrión que Prometheus recoge y almacena | Estándar profesional con historial y alertas, pero requiere varios componentes; el montaje `/hostfs` de este proyecto se inspira en el de `node_exporter`, más restringido (sin submontajes) |
| **Portainer** | Interfaz web de gestión de Docker | Permite **crear y modificar** contenedores; este proyecto lo prohíbe expresamente |

**Qué aporta este proyecto:** una herramienta pequeña que el equipo puede leer y explicar entera,
con un diseño de seguridad explícito (panel sin socket, agente de solo lectura, sin dependencias
nuevas) y que muestra en una sola pantalla el anfitrión y todos los contenedores, también los creados
fuera de ella. No pretende competir en funcionalidad con las herramientas anteriores, que son más
completas.
