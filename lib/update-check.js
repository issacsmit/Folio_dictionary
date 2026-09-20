const GITHUB_API_LATEST =
  'https://api.github.com/repos/issacsmit/Folio_dictionary/releases/latest';
const GITHUB_RELEASES_PAGE =
  'https://github.com/issacsmit/Folio_dictionary/releases';
const RELEASE_URL_PREFIX = 'https://github.com/issacsmit/Folio_dictionary/';
const CHECK_TIMEOUT_MS = 5000;

export {GITHUB_API_LATEST, GITHUB_RELEASES_PAGE, RELEASE_URL_PREFIX};

export function normalizeVersion(value) {
  if (typeof value !== 'string') return null;
  const normalized = value.trim().replace(/^v/iu, '');
  if (!normalized || !/^\d+(?:\.\d+)*$/u.test(normalized)) return null;
  return normalized;
}

export function isNewerVersion(latest, current) {
  const latestParts = normalizeVersion(latest);
  const currentParts = normalizeVersion(current);
  if (!latestParts || !currentParts) return false;
  const latestNumbers = latestParts.split('.').map(Number);
  const currentNumbers = currentParts.split('.').map(Number);
  const length = Math.max(latestNumbers.length, currentNumbers.length);
  for (let index = 0; index < length; index += 1) {
    const latestValue = latestNumbers[index] || 0;
    const currentValue = currentNumbers[index] || 0;
    if (latestValue > currentValue) return true;
    if (latestValue < currentValue) return false;
  }
  return false;
}

export function readCurrentVersion(chromeApi = globalThis.chrome) {
  try {
    return normalizeVersion(chromeApi?.runtime?.getManifest?.()?.version);
  } catch {
    return null;
  }
}

export function sanitizeReleaseUrl(value) {
  if (typeof value !== 'string') return GITHUB_RELEASES_PAGE;
  const trimmed = value.trim();
  if (!trimmed.startsWith(RELEASE_URL_PREFIX) || trimmed.includes('\\')) return GITHUB_RELEASES_PAGE;
  return trimmed;
}

export async function checkForUpdate(options = {}) {
  const current = normalizeVersion(options.currentVersion) || readCurrentVersion(options.chrome);
  const fetchImpl = options.fetch || globalThis.fetch;
  const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0 ? options.timeoutMs : CHECK_TIMEOUT_MS;
  const timerApi = options.timers || globalThis;

  if (!current) {
    return {status: 'unavailable', current: null, code: 'CURRENT_VERSION_UNAVAILABLE', htmlUrl: GITHUB_RELEASES_PAGE};
  }
  if (typeof fetchImpl !== 'function') {
    return {status: 'unavailable', current, code: 'FETCH_UNAVAILABLE', htmlUrl: GITHUB_RELEASES_PAGE};
  }

  let timeoutId;
  try {
    const payload = await Promise.race([
      Promise.resolve(fetchImpl(GITHUB_API_LATEST, {
        method: 'GET',
        headers: {Accept: 'application/vnd.github+json'},
      })).then(async response => {
        if (!response || response.ok !== true) {
          const error = new Error('HTTP_ERROR');
          error.code = `HTTP_${response?.status || 0}`;
          throw error;
        }
        if (typeof response.json !== 'function') throw new Error('BAD_BODY');
        return response.json();
      }),
      new Promise((_resolve, reject) => {
        timeoutId = timerApi.setTimeout(() => {
          const error = new Error('TIMEOUT');
          error.code = 'TIMEOUT';
          reject(error);
        }, timeoutMs);
      }),
    ]);
    const latest = normalizeVersion(payload?.tag_name || payload?.name);
    if (!latest) {
      return {status: 'unavailable', current, code: 'BAD_RELEASE', htmlUrl: GITHUB_RELEASES_PAGE};
    }
    const htmlUrl = sanitizeReleaseUrl(payload?.html_url);
    if (isNewerVersion(latest, current)) return {status: 'available', current, latest, htmlUrl};
    return {status: 'current', current, latest, htmlUrl};
  } catch (error) {
    return {status: 'unavailable', current, code: error?.code || 'NETWORK', htmlUrl: GITHUB_RELEASES_PAGE};
  } finally {
    if (timeoutId !== undefined) timerApi.clearTimeout(timeoutId);
  }
}

export function describeUpdateCheck(result) {
  if (result?.status === 'available') {
    return {
      statusText: `发现新版本 v${result.latest}。`,
      showLink: true,
      linkText: `打开 GitHub 更新说明（v${result.latest}）`,
      href: result.htmlUrl,
      showHowto: true,
    };
  }
  if (result?.status === 'current') {
    return {
      statusText: `已是最新版本（v${result.current}）。`,
      showLink: false,
      linkText: '',
      href: '',
      showHowto: false,
    };
  }
  return {
    statusText: '暂时无法检查更新。',
    showLink: true,
    linkText: '打开 GitHub 发布页',
    href: result?.htmlUrl || GITHUB_RELEASES_PAGE,
    showHowto: true,
  };
}
