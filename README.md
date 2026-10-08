# Igreja Metodista Central de Teresópolis

Site da sede e das subsedes. O passo a passo de Supabase, Brevo e Render entra neste arquivo na etapa de deploy.

Segredos ficam só no `.env` (na sua máquina) e nas Environment Variables do Render. Não os escreva no código, nos testes ou aqui.

## Agora (Parte 1)

1. Copie `env.exemplo` para `.env`, se o `.env` ainda não existir, e preencha os valores.
2. No Supabase, troque a senha do banco em **Project Settings > Database > Reset password** e use a senha nova na `DATABASE_URL` (Session pooler, porta 5432). Caracteres especiais precisam ir codificados (`#` vira `%23`).
3. Abra o **SQL Editor** do Supabase e rode o arquivo `supabase/schema.sql`.
4. Na pasta do projeto, com o ambiente virtual ativo:

```
flask testar-conexao
```

O comando só diz se a conexão funcionou. Ele não mostra senha nem chave.
