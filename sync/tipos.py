"""Aliases de tipo compartilhados entre os módulos da sincronização."""

from psycopg2.extensions import connection

# Conexão psycopg2 aberta por db_chamados.conectar_db().
ConexaoDb = connection

# Número do ticket no Tiflux: int quando vem do Postgres, str quando vem do
# formulário/CLI ou da API. Os dois funcionam nas URLs; não converter.
NumeroTiflux = int | str
