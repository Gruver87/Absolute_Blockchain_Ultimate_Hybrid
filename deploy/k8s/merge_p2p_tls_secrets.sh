#!/bin/sh
# Merge per-pod cert-manager secrets into abs-p2p-tls for legacy entrypoint layout.
# Requires kubectl + RBAC to read secrets in absolute-chain namespace.
set -eu

NS="${NAMESPACE:-absolute-chain}"
OUT_SECRET="${OUT_SECRET:-abs-p2p-tls}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

merge_node() {
  ordinal="$1"
  src_secret="abs-p2p-tls-node-${ordinal}"
  if kubectl -n "${NS}" get secret "${src_secret}" >/dev/null 2>&1; then
    kubectl -n "${NS}" get secret "${src_secret}" -o jsonpath='{.data.tls\.crt}' | base64 -d > "${TMP}/node-${ordinal}.pem"
    kubectl -n "${NS}" get secret "${src_secret}" -o jsonpath='{.data.tls\.key}' | base64 -d > "${TMP}/node-${ordinal}.key"
    echo "merged ${src_secret}"
  else
    echo "skip missing ${src_secret}" >&2
  fi
}

if kubectl -n "${NS}" get secret abs-p2p-ca-tls >/dev/null 2>&1; then
  kubectl -n "${NS}" get secret abs-p2p-ca-tls -o jsonpath='{.data.tls\.crt}' | base64 -d > "${TMP}/ca.pem"
elif kubectl -n "${NS}" get secret "${OUT_SECRET}" >/dev/null 2>&1; then
  kubectl -n "${NS}" get secret "${OUT_SECRET}" -o jsonpath='{.data.ca\.pem}' | base64 -d > "${TMP}/ca.pem" 2>/dev/null || true
fi

for i in 0 1 2; do
  merge_node "${i}"
done

if [ ! -f "${TMP}/node-0.pem" ]; then
  echo "ERROR: no per-pod TLS material found to merge" >&2
  exit 1
fi

kubectl -n "${NS}" create secret generic "${OUT_SECRET}" \
  --from-file="${TMP}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "OK: ${OUT_SECRET} updated in ${NS}"
