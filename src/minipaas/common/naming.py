"""Constantes de nombres y etiquetas compartidas por control plane y agente.

`minipaas.managed=true` se reservará para los recursos de las APLICACIONES de usuario:
el agente solo podrá operar (parar, borrar...) sobre recursos con esa etiqueta.
Los contenedores de la propia plataforma NO la llevan, precisamente para que el agente no
pueda pararse ni borrarse a sí mismo ni borrar el control plane. En su lugar se identifican
con `minipaas.component`.
"""

RESOURCE_PREFIX = "minipaas-"
LABEL_MANAGED = "minipaas.managed"
LABEL_COMPONENT = "minipaas.component"
