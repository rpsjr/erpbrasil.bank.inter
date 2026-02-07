# -*- coding: utf-8 -*-


# from erpbrasil.febraban.boleto.custom_property import CustomProperty
# from erpbrasil.febraban.entidades import Boleto


class BoletoInter:
    """Implementa a Api do BancoInter"""

    @classmethod
    def convert_to(cls, obj, **kwargs):
        obj.__class__ = cls
        obj.__special_init__()
        for key, value in kwargs.items():
            if hasattr(obj, key):
                obj.__dict__[key] = value

    def __init__(
        self,
        sender,
        amount,
        payer,
        issue_date,
        due_date,
        identifier,
        instructions=None,
        mora=None,
        multa=None,
        discount1=None,
        discount2=None,
        discount3=None,
    ):
        self._sender = sender
        self._amount = round(amount,2)
        self._payer = payer
        self._issue_date = issue_date.strftime("%Y-%m-%d")
        self._due_date = due_date.strftime("%Y-%m-%d")
        self._identifier = identifier
        self._instructions = instructions or []

        self.mora = mora or dict(codigoMora="ISENTO", valor=0, taxa=0)
        self.multa = multa or dict(codigoMulta="NAOTEMMULTA", valor=0, taxa=0)
        self.discount1 = discount1 or dict(
            codigoDesconto="NAOTEMDESCONTO", taxa=0, valor=0, data=""
        )
        self.discount2 = discount2 or dict(
            codigoDesconto="NAOTEMDESCONTO", taxa=0, valor=0, data=""
        )
        self.discount3 = discount3 or dict(
            codigoDesconto="NAOTEMDESCONTO", taxa=0, valor=0, data=""
        )

    def _emissao_data(self):
        pagador = dict(
            cpfCnpj=self._payer.identifier,
            nome=self._payer.name,
            email=self._payer.email,
            telefone=self._payer.phone[2:],
            cep=self._payer.address.zipCode,
            numero=self._payer.address.streetNumber,
            complemento=self._payer.address.streetLine2,
            bairro=self._payer.address.district,
            cidade=self._payer.address.city,
            uf=self._payer.address.stateCode,
            endereco=self._payer.address.streetLine1,
            ddd=self._payer.phone[:2],
            tipoPessoa=self._payer.personType,
        )

        def clean_discount(d):
            if not d or d.get("codigoDesconto") == "NAOTEMDESCONTO":
                return dict(codigo="NAOTEMDESCONTO")
            
            res = {"codigo": d["codigoDesconto"]}
            
            # Data is optional but if present must be valid
            if d.get("data"): 
                res["data"] = d["data"]
            
            if d["codigoDesconto"] == "PERCENTUALDATAINFORMADA" or d["codigoDesconto"] == "PERCENTUALVALORNOMINALDIARIO":
                 res["taxa"] = d.get("taxa", 0)
            elif d["codigoDesconto"] == "VALORFIXODATAINFORMADA":
                 res["valor"] = d.get("valor", 0)
            
            # Fallback to include fields if they are non-zero/non-empty just in case logic above misses a type
            if "taxa" not in res and d.get("taxa"):
                res["taxa"] = d["taxa"]
            if "valor" not in res and d.get("valor"):
                res["valor"] = d["valor"]
                
            return res

        def clean_fine(d):
             if not d or d.get("codigoMulta") == "NAOTEMMULTA":
                 return dict(codigo="NAOTEMMULTA")
             
             res = {"codigo": d["codigoMulta"]}
             if d.get("data"): 
                 res["data"] = d["data"]
                 
             if d["codigoMulta"] == "PERCENTUAL":
                 res["taxa"] = d.get("taxa", 0)
             elif d["codigoMulta"] == "VALORFIXO":
                 res["valor"] = d.get("valor", 0)

             if "taxa" not in res and d.get("taxa"):
                 res["taxa"] = d["taxa"]
             if "valor" not in res and d.get("valor"):
                 res["valor"] = d["valor"]
             return res

        def clean_mora(d):
             if not d or d.get("codigoMora") == "ISENTO":
                 return dict(codigo="ISENTO")
             
             res = {"codigo": d["codigoMora"]}
             if d.get("data"): 
                 res["data"] = d["data"]
                 
             if d["codigoMora"] == "TAXAMENSAL":
                 res["taxa"] = d.get("taxa", 0)
             elif d["codigoMora"] == "VALORDIA":
                 res["valor"] = d.get("valor", 0)

             if "taxa" not in res and d.get("taxa"):
                 res["taxa"] = d["taxa"]
             if "valor" not in res and d.get("valor"):
                 res["valor"] = d["valor"]
             return res

        data = dict(
            pagador=pagador,
            seuNumero=self._identifier,
            dataEmissao=self._issue_date,
            dataVencimento=self._due_date,
            valorNominal=self._amount,
            valorAbatimento=0,
            
            multa=clean_fine(self.multa),
            mora=clean_mora(self.mora),
            desconto1=clean_discount(self.discount1),
            desconto2=clean_discount(self.discount2),
            desconto3=clean_discount(self.discount3),
            
            numDiasAgenda="60",
        )

        if self._instructions:
            data["mensagem"] = dict(
                {"linha{}".format(k + 1): v for (k, v) in enumerate(self._instructions)}
            )
        return data
