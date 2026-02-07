# -*- coding: utf-8 -*-
import json
import logging
import requests

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
        result = self._call(
            self.auth.token_boleto_write, requests.post, url=self._api, data=boleto
        )
        return result.content and result.json() or result.ok

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
            params['nome'] = nome
        if email:
            params['email'] = email
        if cpf_cnpj:
            params['cpfCnpj'] = cpf_cnpj
        if nosso_numero:
            params['nossoNumero'] = nosso_numero

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
        url = "{}/{}/pdf".format(self._api, codigo_solicitacao)
        result = self._call(
            self.auth.token_boleto_read,
            requests.get,
            url=url,
        )
        return result.content
