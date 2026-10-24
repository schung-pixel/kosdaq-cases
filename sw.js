// 사례집은 ./review/ 로 이전했습니다. 이 파일은 옛 주소(/kosdaq-cases/)에 남은 서비스워커를 정리하는 용도입니다.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.startsWith('ksc-')).map(k => caches.delete(k)));
    await self.registration.unregister();
    const cs = await self.clients.matchAll({ type: 'window' });
    cs.forEach(c => { const p = new URL(c.url).pathname; if (!p.includes('/deals/') && !p.includes('/review/')) c.navigate(c.url); });
  })());
});
