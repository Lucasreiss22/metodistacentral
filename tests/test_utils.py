"""Testes das funções puras de e-mail e da URL do banco."""

from app.utils import (
    avisos_da_database_url,
    gerar_token_descadastro,
    host_da_database_url,
    mensagem_sem_senha,
    normalizar_database_url,
    normalizar_email,
    opcoes_do_banco,
    problemas_da_database_url,
)


def test_normalizar_email_ignora_espaco_e_maiuscula():
    assert normalizar_email("  Ana@Igreja.COM ") == "ana@igreja.com"


def test_normalizar_email_vazio():
    assert normalizar_email(None) == ""
    assert normalizar_email("   ") == ""


def test_normalizar_database_url_troca_o_driver():
    assert (
        normalizar_database_url("postgres://user:senha@host:5432/postgres")
        == "postgresql+psycopg://user:senha@host:5432/postgres"
    )
    assert (
        normalizar_database_url("postgresql://user:senha@host:5432/postgres")
        == "postgresql+psycopg://user:senha@host:5432/postgres"
    )


def test_normalizar_database_url_preserva_driver_e_vazio():
    pronta = "postgresql+psycopg://user:senha@host:5432/postgres"
    assert normalizar_database_url(pronta) == pronta
    assert normalizar_database_url("  ") == ""
    assert normalizar_database_url(None) == ""


def test_problemas_recusam_url_vazia_sem_inventar_senha():
    assert problemas_da_database_url("")[0].startswith("A variável DATABASE_URL")
    assert problemas_da_database_url(None)


def test_problemas_nao_devolvem_a_senha():
    url = "postgresql://postgres.abc:segredo-unico#1@host:5432/postgres"
    texto = " ".join(problemas_da_database_url(url))
    assert "segredo-unico" not in texto
    assert texto


def test_problemas_apontam_marcador_e_arroba_sem_mostrar_senha():
    url = "postgresql://user:[YOUR-PASSWORD]@host@pooler:5432/postgres"
    texto = " ".join(problemas_da_database_url(url))
    assert "[YOUR-PASSWORD]" not in texto
    assert "marcador de senha" in texto
    assert "%40" in texto


def test_avisos_da_conexao_direta_e_da_porta_6543():
    direta = avisos_da_database_url(
        "postgresql://user:senha@db.abc.supabase.co:5432/postgres"
    )
    assert any("conexão direta" in aviso for aviso in direta)

    transacao = avisos_da_database_url(
        "postgresql://user:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
    )
    assert any("6543" in aviso for aviso in transacao)

    certa = (
        "postgresql://user:senha@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
    )
    assert avisos_da_database_url(certa) == []


def test_host_nao_inclui_usuario_nem_senha():
    url = "postgresql://postgres.abc:segredo@aws-0.pooler.supabase.com:5432/postgres"
    assert host_da_database_url(url) == "aws-0.pooler.supabase.com:5432"
    assert "segredo" not in host_da_database_url(url)
    assert "postgres.abc" not in host_da_database_url(url)


def test_mensagem_de_erro_esconde_senha_codificada():
    url = "postgresql://user:minha%23senha@host:5432/postgres?sslmode=require"
    erro = f"connection failed: {url} (password minha#senha)"
    limpo = mensagem_sem_senha(erro, url)
    assert "minha#senha" not in limpo
    assert "minha%23senha" not in limpo
    assert "***" in limpo
    assert "sslmode=require" in limpo


def test_opcoes_desligam_prepared_statement_so_na_6543():
    sessao = opcoes_do_banco("postgresql://user:senha@host:5432/postgres")
    assert "prepare_threshold" not in sessao["connect_args"]
    assert sessao["pool_pre_ping"] is True

    transacao = opcoes_do_banco("postgresql://user:senha@host:6543/postgres")
    assert transacao["connect_args"]["prepare_threshold"] is None


def test_aceita_os_nomes_novos_das_chaves_do_supabase(monkeypatch):
    from app.config import ler_configuracao

    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_teste")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_teste")
    assert ler_configuracao("SUPABASE_ANON_KEY") == "sb_publishable_teste"
    assert ler_configuracao("SUPABASE_SERVICE_KEY") == "sb_secret_teste"


def test_token_de_descadastro_e_opaco():
    primeiro = gerar_token_descadastro()
    segundo = gerar_token_descadastro()
    assert primeiro != segundo
    assert " " not in primeiro
    assert len(primeiro) >= 32
