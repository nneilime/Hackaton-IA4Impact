import { useLayoutEffect, useRef, useState } from 'react';

const SIZE = 32; // font size; the wordmark is ~30 px tall with its underline
const BASELINE = 24;

/**
 * EnedisPO: an original wordmark in Outfit Bold (live text, font already loaded).
 * "Enedis" in brand blue, "PO" in brand green; under "PO", a short segment of the
 * blue/green/teal/yellow line the map uses for validated routes.
 */
export function Wordmark() {
  const textRef = useRef<SVGTextElement>(null);
  const [m, setM] = useState({ width: 150, poX: 104, poW: 44 });

  useLayoutEffect(() => {
    const measure = () => {
      const t = textRef.current;
      if (!t || t.getNumberOfChars() < 8) return;
      const poX = t.getStartPositionOfChar(6).x;
      const end = t.getEndPositionOfChar(7).x;
      setM({ width: Math.ceil(end + 2), poX, poW: end - poX });
    };
    measure();
    document.fonts.ready.then(measure);
  }, []);

  const segs = ['var(--blue)', 'var(--green)', 'var(--teal)', 'var(--yellow)'];
  const inset = 2; // keeps the round caps inside the letters' width
  const segW = (m.poW - inset * 2) / segs.length;

  return (
    <svg className="wordmark" viewBox={`0 0 ${m.width} 32`} height="32" width={m.width} role="img" aria-label="EnedisPO">
      <text ref={textRef} x="0" y={BASELINE} fontSize={SIZE} fontWeight="700" letterSpacing="-0.6" fontFamily="'Outfit Variable', sans-serif">
        <tspan fill="var(--blue)">Enedis</tspan>
        <tspan fill="var(--green)">PO</tspan>
      </text>
      {segs.map((c, i) => (
        <line
          key={c}
          x1={m.poX + inset + i * segW + (i ? 1.5 : 0)}
          x2={m.poX + inset + (i + 1) * segW - (i < segs.length - 1 ? 1.5 : 0)}
          y1="29.5"
          y2="29.5"
          stroke={c}
          strokeWidth="3"
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}
