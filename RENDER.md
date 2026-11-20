# Subir Emergexia a Render

Emergexia es **un solo servicio**: el mismo servidor de FastAPI da la API (`/api/...`) y las
pantallas. Render lo construye con el `Dockerfile` de esta carpeta y lo configura con
`render.yaml`.

## 1. Antes de empezar (MongoDB Atlas)

1. En Atlas → **Network Access** → *Add IP Address* → `0.0.0.0/0` (permite que Render se conecte).
2. Copia tu cadena de conexión (la misma `MONGO_URI` de `backend/.env`).

## 2. Crear el servicio

1. Sube este repositorio a GitHub (sin `backend/.env`: ya está en `.gitignore`).
2. En Render → **New** → **Blueprint** → elige el repositorio. Render lee `render.yaml`.
3. Te pide estos valores:

| Variable | Qué poner |
|---|---|
| `MONGO_URI` | Tu cadena de conexión de Atlas |
| `ADMIN_USERNAME` | Usuario del primer administrador (solo se usa si la base está vacía) |
| `ADMIN_PASSWORD` | Su contraseña, mínimo 8 caracteres (solo si la base está vacía) |
| `ADMIN_NAME` | Su nombre |

`JWT_SECRET` (la firma de las sesiones) la genera Render solo. `MONGO_DB` ya dice `emergexia`.

4. **Create**. La primera construcción tarda varios minutos. Al terminar, abre la dirección
   que te da Render (algo como `https://emergexia.onrender.com`).

Con tu base actual ya hay usuarios, así que entras con tu cuenta de siempre.

## 3. Qué crea el sistema por su cuenta

Nada, salvo el primer administrador si la base está vacía. Todo lo demás lo capturas tú:

- **Cuentas de la central** (Administrador, Despachador, Supervisor): módulo **Cuentas**.
- **Operadores y paramédicos**: en sus módulos, con su foto, usuario y contraseña.
- **Usuarios que reportan**: cada persona se registra en «Crear una cuenta» (solo puede ser Usuario).
- **Ambulancias**: módulo Ambulancias (Agregar / Editar / Eliminar). Los hospitales ya vienen.

## 4. Bueno saber

- **Plan gratuito**: el servicio se «duerme» tras 15 minutos sin uso y tarda ~1 minuto en
  despertar. Al arrancar entrena los modelos de IA, así que la primera carga es lenta.
- **Spark** no se instala por defecto (necesita Java y mucha memoria); todo lo demás funciona.
  En Configuración → Ver detalles técnicos aparece como no disponible.
- **Mapas y rutas**: las calles se descargan de OpenStreetMap la primera vez que se pide una
  ruta (tarda unos segundos) y luego se guardan mientras el servicio esté encendido.
- **Avisos al instante**: con Atlas funcionan con los *change streams* de MongoDB.
