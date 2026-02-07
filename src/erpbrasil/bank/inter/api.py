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
    "NOSSONUMERO",  # (Default)
    "SEUNUMERO",
    "DATAVENCIMENTO_ASC",
    "DATAVENCIMENTO_DSC",
    "NOMESACADO",
    "VALOR_ASC",
    "VALOR_DSC",
    "STATUS_ASC",
    "STATUS_DSC",
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
        ordenar_por="NOSSONUMERO",
        page=0,
        page_size=100
    ):
        params = dict(
            dataInicial=data_inicial,
            dataFinal=data_final,
            filtrarDataPor=filtrar_data_por,
            ordenarPor=ordenar_por,
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
        # If it's not a UUID, assume it's nossoNumero and try to find the UUID
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', str(codigo_solicitacao)):
             today = datetime.now()
             dt_ini = (today - timedelta(days=365*5)).strftime("%Y-%m-%d")
             dt_fin = (today + timedelta(days=365*2)).strftime("%Y-%m-%d")
             
             # Helper to check if response has cobrancas
             def has_cobrancas(resp):
                 return resp and isinstance(resp, dict) and "cobrancas" in resp and len(resp["cobrancas"]) > 0

             # Prepare candidates for search (padding, unpadding)
             candidates = [str(codigo_solicitacao)]
             if str(codigo_solicitacao).isdigit():
                 candidates.append(str(codigo_solicitacao).zfill(11))
                 candidates.append(str(int(codigo_solicitacao)))
             candidates = list(set(candidates))

             found = False
             for cand in candidates:
                 # Try finding by nossoNumero (VENCIMENTO)
                 cobrancas = self.boleto_consulta(
                     data_inicial=dt_ini,
                     data_final=dt_fin,
                     nosso_numero=cand,
                     filtrar_data_por="VENCIMENTO"
                 )
                 if has_cobrancas(cobrancas):
                      codigo_solicitacao = cobrancas["cobrancas"][0].get("codigoSolicitacao", codigo_solicitacao)
                      found = True
                      break
                 
                 # Try finding by nossoNumero (EMISSAO)
                 cobrancas = self.boleto_consulta(
                     data_inicial=dt_ini,
                     data_final=dt_fin,
                     nosso_numero=cand,
                     filtrar_data_por="EMISSAO"
                 )
                 if has_cobrancas(cobrancas):
                      codigo_solicitacao = cobrancas["cobrancas"][0].get("codigoSolicitacao", codigo_solicitacao)
                      found = True
                      break

             if not found:
                 for cand in candidates:
                     # Try finding by seuNumero (VENCIMENTO)
                     cobrancas = self.boleto_consulta(
                         data_inicial=dt_ini,
                         data_final=dt_fin,
                         seu_numero=cand,
                         filtrar_data_por="VENCIMENTO"
                     )
                     if has_cobrancas(cobrancas):
                          codigo_solicitacao = cobrancas["cobrancas"][0].get("codigoSolicitacao", codigo_solicitacao)
                          found = True
                          break

                     # Try finding by seuNumero (EMISSAO)
                     cobrancas = self.boleto_consulta(
                         data_inicial=dt_ini,
                         data_final=dt_fin,
                         seu_numero=cand,
                         filtrar_data_por="EMISSAO"
                     )
                     if has_cobrancas(cobrancas):
                          codigo_solicitacao = cobrancas["cobrancas"][0].get("codigoSolicitacao", codigo_solicitacao)
                          found = True
                          break
             
        url = "{}/{}/pdf".format(self._api, codigo_solicitacao)
        result = self._call(
            self.auth.token_boleto_read,
            requests.get,
            url=url,
        )
        return result.content
