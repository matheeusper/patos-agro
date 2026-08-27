class ErroPatosAgro(Exception):
    """Erro esperado que pode ser apresentado diretamente ao usuário."""


class ErroEntrada(ErroPatosAgro):
    """Erro nos dados ou no arquivo de entrada."""


class ErroProcessamento(ErroPatosAgro):
    """Erro ao reconstruir as fileiras."""


class ErroSaida(ErroPatosAgro):
    """Erro ao criar o arquivo de saída."""
