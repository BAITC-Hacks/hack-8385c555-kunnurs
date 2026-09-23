const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export async function api(path, { body, timeoutMs = 35000 } = {}) {
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (error?.name === 'TimeoutError') throw new Error('Сервер не ответил вовремя. Попробуйте ещё раз.');
    throw new Error('Нет связи с сервером. Проверьте backend и повторите запрос.');
  }

  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error('Сервер вернул ответ в неожиданном формате.');
  }
  if (!response.ok) {
    const issues = payload?.error?.issues?.map(({ message }) => message).filter(Boolean);
    throw new Error(issues?.length ? issues.join(' ') : payload?.error?.message || `Ошибка сервера (${response.status}).`);
  }
  return payload;
}
