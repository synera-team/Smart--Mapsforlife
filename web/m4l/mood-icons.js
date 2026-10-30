// Mood icons; keys must match MOOD_ICONS in server/m4l_service.py.
const PATHS = {
  compass: '<circle cx="12" cy="12" r="8.5"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
  laptop: '<rect x="4.5" y="5" width="15" height="10" rx="1.5"/><path d="M2.5 19h19M10 17h4"/>',
  leaf: '<path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14z"/><path d="M5 19 13 11"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z"/>',
  bowl: '<path d="M3.5 11.5h17a8.5 8.5 0 0 1-17 0zM8 20h8"/><path d="M9 8c0-1.5 1-2 1-3.5M13 8c0-1.5 1-2 1-3.5M16 4l3-1.5M15 6l5-2"/>',
  coffee: '<path d="M4.5 9h12v5a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5zM16.5 10.5h1.5a2.5 2.5 0 0 1 0 5h-1.8"/><path d="M8 3.5v2.5M12 3.5v2.5"/>',
  music: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 21H20"/>',
  tree: '<path d="M12 21v-5M12 3c3.3 0 6 2.5 6 5.6 0 .7-.1 1.3-.4 1.9A4 4 0 0 1 16 18H8a4 4 0 0 1-1.6-7.5 5 5 0 0 1-.4-1.9C6 5.5 8.7 3 12 3z"/>',
  camera: '<path d="M4 8h3l1.8-2.5h6.4L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
};

export const MOOD_ICON_KEYS = Object.keys(PATHS);

export function moodIcon(key, size = 28) {
  const body = PATHS[key] || PATHS.compass;
  return `<svg class="mood-ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}
