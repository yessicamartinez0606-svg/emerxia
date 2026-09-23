// Verificación de identidad por reconocimiento facial (100% en el navegador).
//
// Usa face-api.js (TensorFlow.js) para: detectar un rostro, calcular su
// "descriptor" (128 números que representan la cara) y comparar dos
// descriptores con distancia euclidiana. No se manda ninguna foto a un
// servicio externo: todo el cálculo ocurre en el navegador del usuario.
//
// Los modelos (pesos ya entrenados) se descargan una sola vez desde un CDN
// público la primera vez que se abren la cámara, y quedan en caché del
// navegador. Si tu red no tiene salida a internet, hospeda la carpeta
// "weights" de face-api.js en frontend/public/models y cambia MODEL_URL a
// '/models'.
import * as faceapi from 'face-api.js'

const MODEL_URL = 'https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights'

// Distancia euclidiana máxima entre dos descriptores para considerarlos la
// misma persona. face-api.js recomienda ~0.6 como umbral general; usamos
// 0.55 para ser un poco más estrictos (menos falsos positivos), ya que aquí
// se usa para confirmar quién sale en la ambulancia.
export const MATCH_THRESHOLD = 0.55

let modelsPromise = null

export function loadFaceModels() {
  if (!modelsPromise) {
    modelsPromise = Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ]).catch((err) => {
      modelsPromise = null // permite reintentar si falló (p. ej. sin internet)
      throw err
    })
  }
  return modelsPromise
}

function imageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('No se pudo leer la imagen capturada.'))
    img.src = dataUrl
  })
}

async function descriptorFromDataUrl(dataUrl) {
  await loadFaceModels()
  const img = await imageFromDataUrl(dataUrl)
  const detection = await faceapi
    .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions())
    .withFaceLandmarks()
    .withFaceDescriptor()
  return detection ? detection.descriptor : null
}

/**
 * Verifica que en la foto sí se vea un rostro (para no aceptar una foto de
 * referencia en blanco, de un objeto, o mal encuadrada). Devuelve:
 *  - { ok: false, reason: 'models' } si no se pudieron cargar los modelos
 *  - { ok: true, hasFace: boolean }
 */
export async function detectFace(dataUrl) {
  let descriptor
  try {
    descriptor = await descriptorFromDataUrl(dataUrl)
  } catch {
    return { ok: false, reason: 'models' }
  }
  return { ok: true, hasFace: !!descriptor }
}

/**
 * Compara la foto de referencia (con la que se registró el operador) contra
 * una foto recién tomada. Devuelve:
 *  - { ok: false, reason: 'no-face-reference' | 'no-face-capture' | 'models' }
 *  - { ok: true, match: boolean, distance: number }
 */
export async function compareFaces(referenceDataUrl, capturedDataUrl) {
  let referenceDescriptor
  let capturedDescriptor
  try {
    ;[referenceDescriptor, capturedDescriptor] = await Promise.all([
      descriptorFromDataUrl(referenceDataUrl),
      descriptorFromDataUrl(capturedDataUrl),
    ])
  } catch {
    return { ok: false, reason: 'models' }
  }
  if (!referenceDescriptor) return { ok: false, reason: 'no-face-reference' }
  if (!capturedDescriptor) return { ok: false, reason: 'no-face-capture' }

  const distance = faceapi.euclideanDistance(referenceDescriptor, capturedDescriptor)
  return { ok: true, match: distance <= MATCH_THRESHOLD, distance }
}

// Los descriptores de las fotos de referencia se guardan en memoria para no
// recalcularlos en cada intento (calcularlos es lo más lento del proceso).
const descriptorCache = new Map()

async function cachedDescriptor(dataUrl) {
  if (descriptorCache.has(dataUrl)) return descriptorCache.get(dataUrl)
  const descriptor = await descriptorFromDataUrl(dataUrl)
  descriptorCache.set(dataUrl, descriptor)
  return descriptor
}

/**
 * Identifica a quién pertenece un rostro entre varios candidatos (p. ej. todos
 * los operadores registrados): compara la foto recién tomada contra la foto de
 * referencia de cada uno y se queda con el más parecido, siempre que pase el
 * umbral. `candidates` es una lista de { foto, ...datos } (los datos se
 * devuelven tal cual en `candidate`). Devuelve:
 *  - { ok: false, reason: 'no-candidates' | 'no-face-capture' | 'models' }
 *  - { ok: true, match: boolean, candidate, distance }  (candidate es el más
 *    cercano aunque no llegue al umbral, para poder mostrar la distancia)
 */
export async function identifyFace(capturedDataUrl, candidates) {
  const withPhoto = candidates.filter((c) => c.foto)
  if (withPhoto.length === 0) return { ok: false, reason: 'no-candidates' }

  let capturedDescriptor
  let descriptors
  try {
    capturedDescriptor = await descriptorFromDataUrl(capturedDataUrl)
    if (!capturedDescriptor) return { ok: false, reason: 'no-face-capture' }
    descriptors = await Promise.all(withPhoto.map((c) => cachedDescriptor(c.foto)))
  } catch {
    return { ok: false, reason: 'models' }
  }

  let best = null
  withPhoto.forEach((candidate, i) => {
    if (!descriptors[i]) return // su foto de referencia no tiene un rostro detectable
    const distance = faceapi.euclideanDistance(descriptors[i], capturedDescriptor)
    if (!best || distance < best.distance) best = { candidate, distance }
  })
  if (!best) return { ok: false, reason: 'no-candidates' }

  return { ok: true, match: best.distance <= MATCH_THRESHOLD, candidate: best.candidate, distance: best.distance }
}
