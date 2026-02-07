# -*- coding: utf-8 -*-
import json
import logging
import requests
import re
from datetime import datetime, timedelta

from .auth import Auth

FILTRAR_POR = [
    "TODOS",
    "VENCIDOSAVENCER",
    "EXPIRADOS",
    "PAGOS",
    "TODOSBAIXADOS",
]

ORDENAR_CONSULTA_POR = [
    "PESSOA_PAGADORA",
    "TIPO_COBRANCA",
    "CODIGO_COBRANCA",
    "IDENTIFICADOR",
    "DATA_EMISSAO",
    "DATA_VENCIMENTO",
    "VALOR",
    "STATUS"
]

_logger = logging.getLogger(__name__)


class ApiInter(object):
    """Implementa a Api do Inter"""

    # _api = 'https://apis.bancointer.com.br:8443/openbanking/v1/certificado/boletos'
    # _api = "https://cdpj.partners.bancointer.com.br/cobranca/v2/boletos/"
    _api = "https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas"

    def __init__(self, cert, conta_corrente, clientId, clientSecret):
        self._cert = cert
        self.conta_corrente = conta_corrente
        self.auth = Auth(
            clientId,
            # "50acb448-5107-4f57-81ea-54a615c5da0a",
            clientSecret,
            # "0a0275ff-4fcc-4f7f-a092-edcbb5bb6bd8",
        )
        self.auth.generate_token_boleto_write("boleto-cobranca.write", self._cert)
        self.auth.generate_token_boleto_read("boleto-cobranca.read", self._cert)

    def _prepare_headers(self, token):
        return {
            "content-type": "application/json",
            "x-inter-conta-corrente": self.conta_corrente,
            "Authorization": "Bearer " + token,
        }

    def _call(self, token, http_request, url, params=None, data=None, **kwargs):
        debug1 = self._prepare_headers(token)
        debug2 = json.dumps(data or {})
        debug3 = params or {}
        response = http_request(
            url,
            headers=self._prepare_headers(token),
            params=params or {},
            data=json.dumps(data or {}),
            cert=self._cert,
            verify=True,
            **kwargs,
        )
        if response.status_code > 299:
            # error = response.json()
            error = response  # .json()
            # message = '%s - Código %s' % (
            #    response.status_code,
            #    error.get('error-code')
            # )
            # raise Exception(message)
            _logger.error("DEBUG HEADER: {}".format(debug1))
            _logger.error("DEBUG DATA: {}".format(debug2))
            _logger.error("DEBUG PARAMS: {}".format(debug3))
            raise Exception(
                [str(response.text), response.status_code, debug1, debug2, debug3]
            )
        return response

    def _find_uuid_from_code(self, code):
        """Helper to find UUID if code is nossoNumero or seuNumero"""
        if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', str(code)):
            return str(code)

        today = datetime.now()
        dt_ini = (today - timedelta(days=365*5)).strftime("%Y-%m-%d")
        dt_fin = (today + timedelta(days=365*2)).strftime("%Y-%m-%d")
        
        target = str(code).lstrip('0')

        def find_in_list(cobrancas):
            if cobrancas and isinstance(cobrancas, dict) and "cobrancas" in cobrancas:
                for item in cobrancas["cobrancas"]:
                    # Helper to get uuid from item
                    uuid = item.get("cobranca", {}).get("codigoSolicitacao") or item.get("codigoSolicitacao")
                    if not uuid: continue
                    
                    # Check boleto.nossoNumero
                    nn = item.get("boleto", {}).get("nossoNumero", "")
                    if str(nn).lstrip('0') == target:
                        return uuid
                    
                    # Check cobranca.seuNumero
                    sn = item.get("cobranca", {}).get("seuNumero", "")
                    if str(sn).lstrip('0') == target:
                        return uuid
                    
                    # Fallback checks
                    if str(item.get("nossoNumero", "")).lstrip('0') == target:
                        return uuid
                    if str(item.get("seuNumero", "")).lstrip('0') == target:
                        return uuid
            return None

        # Strategy 1: Try searching by nossoNumero/seuNumero with variations
        candidates = [str(code)]
        if str(code).isdigit():
             candidates.append(str(code).zfill(11))
             candidates.append(str(int(code)))
        candidates = list(set(candidates))

        sort_opts = ["CODIGO_COBRANCA", "DATA_EMISSAO"] 

        for cand in candidates:
             for sort_by in sort_opts:
                 # Try finding by nossoNumero (VENCIMENTO)
                 cobrancas = self.boleto_consulta(
                     data_inicial=dt_ini, data_final=dt_fin,
                     nosso_numero=cand, filtrar_data_por="VENCIMENTO",
                     ordenar_por=sort_by, type_ordenacao="DESC"
                 )
                 uuid = find_in_list(cobrancas)
                 if uuid: return uuid
                 
                 # Try finding by nossoNumero (EMISSAO)
                 cobrancas = self.boleto_consulta(
                     data_inicial=dt_ini, data_final=dt_fin,
                     nosso_numero=cand, filtrar_data_por="EMISSAO",
                     ordenar_por=sort_by, type_ordenacao="DESC"
                 )
                 uuid = find_in_list(cobrancas)
                 if uuid: return uuid

        for cand in candidates:
             # Try finding by seuNumero (VENCIMENTO)
             cobrancas = self.boleto_consulta(
                 data_inicial=dt_ini, data_final=dt_fin,
                 seu_numero=cand, filtrar_data_por="VENCIMENTO",
                 ordenar_por="CODIGO_COBRANCA", type_ordenacao="DESC"
             )
             uuid = find_in_list(cobrancas)
             if uuid: return uuid

             # Try finding by seuNumero (EMISSAO)
             cobrancas = self.boleto_consulta(
                 data_inicial=dt_ini, data_final=dt_fin,
                 seu_numero=cand, filtrar_data_por="EMISSAO",
                 ordenar_por="CODIGO_COBRANCA", type_ordenacao="DESC"
             )
             uuid = find_in_list(cobrancas)
             if uuid: return uuid

        # Strategy 2: Generic search (if filters are broken/ignored)
        # Fetch recent 100 items by EMISSAO DESC
        cobrancas = self.boleto_consulta(
             data_inicial=dt_ini, data_final=dt_fin,
             filtrar_data_por="EMISSAO",
             ordenar_por="CODIGO_COBRANCA", type_ordenacao="DESC",
             page_size=100
        )
        uuid = find_in_list(cobrancas)
        if uuid: return uuid
        
        return str(code)

    def boleto_inclui(self, boleto):
        """POST

        :param boleto:
        :return:
        """
        try:
            result = self._call(
                self.auth.token_boleto_write, requests.post, url=self._api, data=boleto
            )
            data = result.content and result.json() or {}
        except Exception as e:
            data = None
            if isinstance(e.args[0], list) and len(e.args[0]) > 0:
                try:
                    error_json = json.loads(e.args[0][0])
                    detail = error_json.get("detail", "")
                    # Regex to extract UUID: código de solicitação: uuid.
                    match = re.search(r"código de solicitação:\s*([a-f0-9\-]+)", detail)
                    if match:
                        data = {"codigoSolicitacao": match.group(1)}
                except:
                    pass
            if not data:
                raise e

        if isinstance(data, dict) and data.get("codigoSolicitacao"):
            detail = self.boleto_recupera(data["codigoSolicitacao"])
            if isinstance(detail, dict):
                # Flatten the response for compatibility
                if "boleto" in detail:
                    data.update(detail["boleto"])
                if "cobranca" in detail:
                    data.update(detail["cobranca"])
        return data or (result.ok if 'result' in locals() else False)

    def boleto_consulta(
        self,
        data_inicial=None,
        data_final=None,
        filtrar_data_por="VENCIMENTO",
        situacao=None,
        nome=None,
        email=None,
        cpf_cnpj=None,
        nosso_numero=None,
        seu_numero=None,
        ordenar_por="CODIGO_COBRANCA",
        type_ordenacao="ASC",
        page=0,
        page_size=100
    ):
        params = dict(
            dataInicial=data_inicial,
            dataFinal=data_final,
            filtrarDataPor=filtrar_data_por,
            ordenarPor=ordenar_por,
            tipoOrdenacao=type_ordenacao,
            pagina=page,
            tamanhoPagina=page_size
        )
        if situacao:
            params['situacao'] = situacao
        if nome:
            params['pessoaPagadora'] = nome
        if email:
            params['email'] = email
        if cpf_cnpj:
            params['cpfCnpjPessoaPagadora'] = cpf_cnpj
        if nosso_numero:
            params['nossoNumero'] = nosso_numero
        if seu_numero:
            params['seuNumero'] = seu_numero

        result = self._call(
            self.auth.token_boleto_read,
            requests.get,
            url=self._api,
            params=params,
        )
        return result.content and result.json() or result.ok

    def boleto_recupera(self, codigo_solicitacao):

        _url = f"{self._api}/{codigo_solicitacao}"

        result = self._call(
            self.auth.token_boleto_read,
            requests.get,
            url=_url,
        )

        return result.content and result.json() or result.ok

    def boleto_baixa(self, codigo_solicitacao, motivoCancelamento):
        """POST
        https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/{codigoSolicitacao}/cancelar


        :param codigo_solicitacao:
        :return:
        """
        codigo_solicitacao = self._find_uuid_from_code(codigo_solicitacao)
        url = "{}/{}/cancelar".format(self._api, codigo_solicitacao)
        result = self._call(
            self.auth.token_boleto_write,
            requests.post,
            url=url,
            data=dict(
                motivoCancelamento=motivoCancelamento,
            ),
        )
        return result.content and result.json() or result.ok

    def boleto_pdf(self, codigo_solicitacao):
        """GET
        https://cdpj.partners.bancointer.com.br/cobranca/v3/cobrancas/
            {codigoSolicitacao}/pdf

        :param codigo_solicitacao:
        :return:
        """
        codigo_solicitacao = self._find_uuid_from_code(codigo_solicitacao)
        
        url = "{}/{}/pdf".format(self._api, codigo_solicitacao)
        result = self._call(
            self.auth.token_boleto_read,
            requests.get,
            url=url,
        )
        return result.content
