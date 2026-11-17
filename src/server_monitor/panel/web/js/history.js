// Histórico de métricas en memoria para las gráficas (10 minutos, sin inventar puntos).

export const WINDOW_MS = 10 * 60 * 1000;
const MAX_SAMPLES = 120;

export function createHistory() {
  const samples = []; // { t, cpu, ram, rx, tx }: rx/tx en bytes por segundo o null
  let lastNetwork = null;

  function add(metrics) {
    const t = Date.parse(metrics.collected_at);
    if (Number.isNaN(t)) return false;
    if (samples.length && t <= samples[samples.length - 1].t) return false;

    // La red llega como contadores acumulados: velocidad = diferencia de bytes / diferencia de tiempo.
    let rx = null;
    let tx = null;
    const net = metrics.network;
    if (net) {
      if (lastNetwork) {
        const seconds = (t - lastNetwork.t) / 1000;
        const dRx = net.rx_bytes - lastNetwork.rx;
        const dTx = net.tx_bytes - lastNetwork.tx;
        // un contador que baja (reinicio) deja un hueco en la gráfica
        if (seconds > 0 && dRx >= 0 && dTx >= 0) { rx = dRx / seconds; tx = dTx / seconds; }
      }
      lastNetwork = { t, rx: net.rx_bytes, tx: net.tx_bytes };
    } else {
      lastNetwork = null;
    }

    samples.push({ t, cpu: metrics.cpu.percent, ram: metrics.memory.percent, rx, tx });
    while (samples.length > MAX_SAMPLES || (samples.length && samples[0].t < t - WINDOW_MS)) samples.shift();
    return true;
  }

  return { samples, add };
}
