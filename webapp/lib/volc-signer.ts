/**
 * 火山引擎 Volcengine Visual API V4 HMAC-SHA256 签名 (TypeScript port).
 *
 * 端口自 src/common/volc_signer.py (Python production-verified).
 *
 * 锁定:
 *   - 算法: HMAC-SHA256
 *   - 区域: cn-north-1
 *   - 服务: cv
 *   - Host: visual.volcengineapi.com
 *   - 签名头: content-type;host;x-content-sha256;x-date
 *   - Credential scope: <yyyymmdd>/cn-north-1/cv/request
 *
 * 使用 Node.js 18+ 原生 crypto，零依赖。
 */
import crypto from 'node:crypto';

const REGION = 'cn-north-1';
const SERVICE = 'cv';
const HOST = 'visual.volcengineapi.com';
const ALGORITHM = 'HMAC-SHA256';

export interface SignedRequest {
  method: 'POST';
  url: string;
  headers: Record<string, string>;
  body: Buffer;
}

function sha256Hex(data: Buffer | string): string {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function hmacSha256(key: Buffer | string, msg: string): Buffer {
  return crypto.createHmac('sha256', key).update(msg, 'utf8').digest();
}

function deriveSigningKey(
  secretKey: string,
  datestamp: string,
  region: string,
  service: string,
): Buffer {
  const kDate = hmacSha256(secretKey, datestamp);
  const kRegion = hmacSha256(kDate, region);
  const kService = hmacSha256(kRegion, service);
  return hmacSha256(kService, 'request');
}

function rfc3986EncodeURIComponent(str: string): string {
  // V4 signing requires RFC 3986 percent-encoding (`!*'()` must be encoded;
  // `-_.~` are safe). JS encodeURIComponent leaves `!*'()` unencoded, so patch.
  return encodeURIComponent(str).replace(
    /[!*'()]/g,
    (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase(),
  );
}

function canonicalQueryString(params: Record<string, string>): string {
  const keys = Object.keys(params).sort();
  if (keys.length === 0) return '';
  return keys
    .map((k) => `${rfc3986EncodeURIComponent(k)}=${rfc3986EncodeURIComponent(params[k])}`)
    .join('&');
}

export interface SignRequestOpts {
  accessKey: string;
  secretKey: string;
  action: string;
  version: string;
  body: Buffer | string;
  extraQuery?: Record<string, string>;
}

export function signRequest(opts: SignRequestOpts): SignedRequest {
  const bodyBuf = Buffer.isBuffer(opts.body) ? opts.body : Buffer.from(opts.body, 'utf8');

  const now = new Date();
  const yyyy = now.getUTCFullYear().toString().padStart(4, '0');
  const mm = (now.getUTCMonth() + 1).toString().padStart(2, '0');
  const dd = now.getUTCDate().toString().padStart(2, '0');
  const HH = now.getUTCHours().toString().padStart(2, '0');
  const MM = now.getUTCMinutes().toString().padStart(2, '0');
  const SS = now.getUTCSeconds().toString().padStart(2, '0');
  const amzdate = `${yyyy}${mm}${dd}T${HH}${MM}${SS}Z`;
  const datestamp = `${yyyy}${mm}${dd}`;

  const query: Record<string, string> = { Action: opts.action, Version: opts.version };
  if (opts.extraQuery) {
    for (const [k, v] of Object.entries(opts.extraQuery)) {
      if (v !== undefined && v !== null) query[k] = String(v);
    }
  }
  const canonicalQS = canonicalQueryString(query);

  const payloadHash = sha256Hex(bodyBuf);

  const canonicalHeaders =
    'content-type:application/json\n' +
    `host:${HOST}\n` +
    `x-content-sha256:${payloadHash}\n` +
    `x-date:${amzdate}\n`;
  const signedHeaders = 'content-type;host;x-content-sha256;x-date';

  const canonicalRequest = [
    'POST',
    '/',
    canonicalQS,
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join('\n');

  const credentialScope = `${datestamp}/${REGION}/${SERVICE}/request`;
  const stringToSign = [
    ALGORITHM,
    amzdate,
    credentialScope,
    sha256Hex(canonicalRequest),
  ].join('\n');

  const signingKey = deriveSigningKey(opts.secretKey, datestamp, REGION, SERVICE);
  const signature = crypto.createHmac('sha256', signingKey).update(stringToSign, 'utf8').digest('hex');

  const authorization =
    `${ALGORITHM} ` +
    `Credential=${opts.accessKey}/${credentialScope}, ` +
    `SignedHeaders=${signedHeaders}, ` +
    `Signature=${signature}`;

  return {
    method: 'POST',
    url: `https://${HOST}/?${canonicalQS}`,
    headers: {
      'Content-Type': 'application/json',
      Host: HOST,
      'X-Date': amzdate,
      'X-Content-Sha256': payloadHash,
      Authorization: authorization,
    },
    body: bodyBuf,
  };
}
