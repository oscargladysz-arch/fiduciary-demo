/* Pins: the rows a reader is collecting for a committee document.
 *
 * A pin is (fund, cell). It is kept in this browser only, which the packet
 * says out loud, because nothing here is stored on a server. A duplicate pin
 * is refused rather than added twice, removing one offers an undo, and every
 * pin carries the row's element name so a list of pins reads as a list of
 * findings rather than a list of numbers. */
import { useCallback, useEffect, useState } from "react";

export interface Pin { productKey: string; fundName: string; cell: string; element: string }

const KEY = "tark.pins";
const listeners = new Set<() => void>();

function read(): Pin[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((p) => p && p.productKey && p.cell) : [];
  } catch { return []; }
}

function write(pins: Pin[]) {
  try { localStorage.setItem(KEY, JSON.stringify(pins)); } catch { /* storage may be blocked */ }
  for (const l of listeners) l();
}

export function isPinned(pins: Pin[], productKey: string, cell: string): boolean {
  return pins.some((p) => p.productKey === productKey && p.cell === cell);
}

export function usePins() {
  const [pins, set] = useState<Pin[]>(read);
  useEffect(() => {
    const l = () => set(read());
    listeners.add(l);
    return () => { listeners.delete(l); };
  }, []);

  const add = useCallback((pin: Pin): "added" | "already" => {
    const now = read();
    if (isPinned(now, pin.productKey, pin.cell)) return "already";
    write([...now, pin]);
    return "added";
  }, []);

  const remove = useCallback((productKey: string, cell: string): Pin | null => {
    const now = read();
    const gone = now.find((p) => p.productKey === productKey && p.cell === cell) || null;
    write(now.filter((p) => !(p.productKey === productKey && p.cell === cell)));
    return gone;
  }, []);

  const restore = useCallback((pin: Pin, at: number) => {
    const now = read();
    write([...now.slice(0, at), pin, ...now.slice(at)]);
  }, []);

  const move = useCallback((from: number, to: number) => {
    const now = read();
    if (to < 0 || to >= now.length || from === to) return;
    const next = [...now];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    write(next);
  }, []);

  const clear = useCallback(() => write([]), []);

  return { pins, add, remove, restore, move, clear };
}
