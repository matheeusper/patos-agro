import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class SessaoProcessamento:
    dados: object
    nome_arquivo: str
    ultimo_acesso: float


class ArmazenamentoSessoes:
    def __init__(self, limite=3, validade_segundos=30 * 60, relogio=None):
        self.limite = limite
        self.validade_segundos = validade_segundos
        self.relogio = relogio or time.monotonic
        self._sessoes = OrderedDict()
        self._trava = threading.Lock()

    def _remover_expiradas(self, agora):
        expiradas = [
            identificador
            for identificador, sessao in self._sessoes.items()
            if agora - sessao.ultimo_acesso >= self.validade_segundos
        ]
        for identificador in expiradas:
            self._sessoes.pop(identificador, None)

    def criar(self, dados, nome_arquivo):
        with self._trava:
            agora = self.relogio()
            self._remover_expiradas(agora)
            while len(self._sessoes) >= self.limite:
                self._sessoes.popitem(last=False)
            identificador = uuid.uuid4().hex
            self._sessoes[identificador] = SessaoProcessamento(dados, nome_arquivo, agora)
            return identificador

    def obter(self, identificador):
        with self._trava:
            agora = self.relogio()
            self._remover_expiradas(agora)
            sessao = self._sessoes.get(identificador)
            if sessao is None:
                return None
            sessao.ultimo_acesso = agora
            self._sessoes.move_to_end(identificador)
            return sessao

    def remover(self, identificador):
        with self._trava:
            return self._sessoes.pop(identificador, None) is not None

    def quantidade(self):
        with self._trava:
            self._remover_expiradas(self.relogio())
            return len(self._sessoes)
