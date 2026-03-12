"""
license.py - Sistema de licenciamento do Ross PDF Editor.

- Machine ID: SHA256 de MAC + hostname + platform
- Licença: payload JSON assinado com HMAC-SHA256, codificado em base32
- Formato visual: PDF-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
- Validação híbrida: Online (Supabase) + Offline (chave local)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import uuid
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Optional

# ─── Chave secreta (hardcoded — não compartilhe este código) ─────────────────
_SECRET_KEY = b"RossPDFEditor@License#2026$Ross&Seguranca!"


# ─── Machine ID ──────────────────────────────────────────────────────────────

def get_machine_id() -> str:
    """
    Retorna o fingerprint único desta máquina.
    Combina: MAC address + hostname + sistema operacional.
    Formato de saída: XXXX-XXXX-XXXX-XXXX (16 caracteres hex maiúsculos)
    """
    try:
        mac = str(uuid.getnode())
        hostname = platform.node()
        system = platform.system() + platform.release()
        raw = f"{mac}|{hostname}|{system}"
        digest = hashlib.sha256(raw.encode()).hexdigest().upper()
        chars = digest[:16]
        return f"{chars[0:4]}-{chars[4:8]}-{chars[8:12]}-{chars[12:16]}"
    except Exception:
        return "0000-0000-0000-0000"


def _raw_machine_id() -> str:
    """Retorna o machine ID completo (SHA256 hex) para uso interno."""
    try:
        mac = str(uuid.getnode())
        hostname = platform.node()
        system = platform.system() + platform.release()
        raw = f"{mac}|{hostname}|{system}"
        return hashlib.sha256(raw.encode()).hexdigest().upper()
    except Exception:
        return "0" * 64


# ─── Geração de licença ───────────────────────────────────────────────────────

def gerar_licenca(machine_id_display: str, meses: int = 1) -> str:
    """
    Gera uma chave de licença assinada para o machine_id informado.
    """
    expiry = (date.today() + timedelta(days=30 * meses)).isoformat()
    mid = machine_id_display.replace("-", "").upper()

    payload = json.dumps({
        "mid": mid,
        "exp": expiry,
        "ver": 1,
    }, separators=(",", ":"))

    sig = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest().upper()
    combined = f"{payload}||{sig}"
    encoded = base64.b32encode(combined.encode()).decode().rstrip("=")

    groups = [encoded[i : i + 5] for i in range(0, len(encoded), 5)]
    key = "PDF-" + "-".join(groups)
    return key


# ─── Erros ────────────────────────────────────────────────────────────────────

class LicenseError(Exception):
    """Erro específico de licença inválida ou expirada."""


# ─── Validação Online (Supabase) ─────────────────────────────────────────────

def verificar_licenca_online(machine_id: str) -> Optional[dict]:
    """
    Tenta validar a licença pela API REST do Supabase.
    Retorna dict com dados se válido, None se não encontrado ou erro.
    """
    try:
        supabase_url = None
        supabase_key = None
        supabase_table = None

        try:
            from version import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE
            supabase_url = SUPABASE_URL
            supabase_key = SUPABASE_KEY
            supabase_table = SUPABASE_TABLE
        except ImportError:
            try:
                import sys
                from pathlib import Path
                root = Path(__file__).parent.parent
                if str(root) not in sys.path:
                    sys.path.append(str(root))
                from version import SUPABASE_URL, SUPABASE_KEY, SUPABASE_TABLE
                supabase_url = SUPABASE_URL
                supabase_key = SUPABASE_KEY
                supabase_table = SUPABASE_TABLE
            except Exception:
                pass

        if not all([supabase_url, supabase_key, supabase_table]):
            return None

        mid_clean = machine_id.strip().upper()

        # Consulta: Buscar licença pelo Machine ID
        query_params = urllib.parse.urlencode({"machine_id": f"eq.{mid_clean}", "select": "*" })
        url = f"{supabase_url}/rest/v1/{supabase_table}?{query_params}"

        headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }

        req = urllib.request.Request(url, headers=headers, method="GET")

        with urllib.request.urlopen(req, timeout=15) as response:
            if response.getcode() == 200:
                rows = json.loads(response.read().decode())

                if not rows:
                    raise LicenseError("status:novo")

                data = rows[0]
                status_bd = str(data.get("status", "")).strip().lower()
                plano_bd = str(data.get("plan", "")).strip().lower()

                if status_bd != "ativo":
                    raise LicenseError(
                        f"Sua licença está {status_bd.upper()}. "
                        "Entre em contato com o administrador."
                    )

                # Validação de Expiração
                exp_str = data.get("expiration")
                expiry_date = None
                display_exp = "Vitalício"

                if exp_str:
                    try:
                        date_clean = str(exp_str).replace("T", " ").split(" ")[0]
                        expiry_date = datetime.strptime(date_clean, "%Y-%m-%d").date()
                        display_exp = expiry_date.strftime("%d/%m/%Y")
                    except Exception:
                        pass

                if expiry_date and date.today() > expiry_date:
                    raise LicenseError("Sua licença expirou. Entre em contato para renovar.")

                # Atualizar Last Login
                try:
                    update_url = f"{supabase_url}/rest/v1/{supabase_table}?id=eq.{data['id']}"
                    update_data = json.dumps({"last_login": "now()"}).encode()
                    update_req = urllib.request.Request(
                        update_url, data=update_data, headers=headers, method="PATCH"
                    )
                    with urllib.request.urlopen(update_req, timeout=5) as u_res:
                        if u_res.getcode() in (200, 204):
                            pass
                except Exception:
                    pass

                dias_restantes = 8888
                if expiry_date:
                    dias_restantes = (expiry_date - date.today()).days

                return {
                    "valido": True,
                    "expiry": display_exp,
                    "dias_restantes": dias_restantes,
                    "cliente": data.get("name", "Cliente Online"),
                    "plano": data.get("plan", "Trial").upper(),
                    "metodo": "online"
                }
            else:
                pass
    except LicenseError:
        raise
    except Exception:
        pass
    return None


# ─── Validação Offline (chave local) ─────────────────────────────────────────

def _decode_key(key: str) -> tuple[str, str]:
    """Decodifica a chave no formato PDF-XXXXX-... e retorna (payload, sig)."""
    key = key.strip().upper()
    if not key.startswith("PDF-"):
        raise LicenseError("Chave inválida: prefixo incorreto.")

    body = key[4:].replace("-", "")
    pad = (8 - len(body) % 8) % 8
    try:
        decoded = base64.b32decode(body + "=" * pad).decode()
    except Exception as exc:
        raise LicenseError("Chave inválida: não foi possível decodificar.") from exc

    if "||" not in decoded:
        raise LicenseError("Chave inválida: estrutura incorreta.")

    payload_str, sig = decoded.split("||", 1)
    return payload_str, sig


def validar_licenca(key: str) -> dict:
    """
    Valida a chave de licença para esta máquina de forma HÍBRIDA.
    1. Tenta Online via MachineID.
    2. Se não disponível, tenta validar a chave (key) offline.
    """
    mid_display = get_machine_id()

    # 1. TENTATIVA ONLINE (Prioridade)
    online_res = verificar_licenca_online(mid_display)
    if online_res:
        return {
            "valido": True,
            "expiry": online_res["expiry"],
            "dias_restantes": online_res.get("dias_restantes", 30),
            "plano": online_res.get("plano", "TRIAL"),
            "cliente": online_res.get("cliente", "Cliente"),
            "metodo": "online"
        }

    # 2. TENTATIVA OFFLINE (Fallback)
    if not key:
        raise LicenseError("Nenhuma licença encontrada. Entre em contato para ativar.")

    payload_str, sig_recebida = _decode_key(key)

    sig_esperada = hmac.new(
        _SECRET_KEY, payload_str.encode(), hashlib.sha256
    ).hexdigest().upper()

    if not hmac.compare_digest(sig_recebida, sig_esperada):
        raise LicenseError("Chave inválida: assinatura incorreta.")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as exc:
        raise LicenseError("Chave inválida: dados corrompidos.") from exc

    mid_licenca = payload.get("mid", "").upper()
    mid_maquina = _raw_machine_id()[:16]
    if mid_licenca != mid_maquina:
        raise LicenseError(
            "Licença inválida para esta máquina.\n"
            "Esta chave foi gerada para outro computador."
        )

    exp_str = payload.get("exp", "")
    try:
        expiry = datetime.strptime(exp_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise LicenseError("Chave inválida: data de expiração corrompida.") from exc

    today = date.today()
    if today > expiry:
        dias_vencida = (today - expiry).days
        raise LicenseError(
            f"Licença expirada há {dias_vencida} dia(s).\n"
            "Entre em contato para renovar sua licença."
        )

    dias_restantes = (expiry - today).days
    return {
        "valido": True,
        "expiry": expiry.strftime("%d/%m/%Y"),
        "dias_restantes": dias_restantes,
        "plano": "OFFLINE",
        "metodo": "offline"
    }


# ─── Persistência ─────────────────────────────────────────────────────────────

def salvar_licenca(key: str, settings: dict) -> None:
    """Salva a chave de licença nas settings."""
    settings["license_key"] = key.strip().upper()


def carregar_licenca(settings: dict) -> Optional[str]:
    """Carrega a chave de licença das settings. Retorna None se não houver."""
    key = settings.get("license_key", "")
    return key if key else None


def verificar_licenca_settings(settings: dict) -> Optional[dict]:
    """Verifica se há uma licença válida nas settings."""
    key = carregar_licenca(settings)
    if not key:
        return None
    try:
        return validar_licenca(key)
    except LicenseError:
        return None
