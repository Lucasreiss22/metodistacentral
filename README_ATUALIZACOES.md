# Atualizações: acesso da equipe, informativos e LGPD

O site continua em Flask, com o banco descrito em `supabase/schema.sql`. A Bíblia online saiu do ar. O login do painel deixou de usar o Supabase Auth: a senha fica só como hash PBKDF2 na tabela `administradores`.

## 1. Banco

No SQL Editor do Supabase, rode de novo o arquivo `supabase/schema.sql`. O processo do site também aplica essas mesmas colunas ao subir, quando a `DATABASE_URL` aponta para o Postgres. Assim um deploy novo cobre o banco que já existia, sem esperar o SQL Editor.

O script pode ser repetido. Ele não apaga tabela. Em um banco que já existia, ele acrescenta:

- colunas de opt-in e de número internacional em `congregados`
- coluna `categoria` em `eventos` (`geral` ou `empreendedores`)
- colunas `senha_hash`, `eh_super_admin` e `ministerio` em `administradores`
- tabelas `administrador_permissoes` e `solicitacoes_lgpd`

Não havia tabela da Bíblia. Nada foi removido do banco por causa dela.

Quem já recebia notícias e ainda estava com opt-in pendente passa a `confirmado`, com origem `cadastro_anterior`.

Na pasta do projeto, com o ambiente virtual ativo, rode também:

```
flask preparar-congregados
```

Esse comando preenche `whatsapp_e164` (55 + DDD + número) nos cadastros antigos. O schema já marca o opt-in; o comando repete essa marcação para quem ainda estiver pendente.

## 2. Primeiro administrador

E-mail: `admin@metodistacentral.local`

Senha: `Central@2026`

Esses são os valores usados quando `ADMIN_EMAIL` e `ADMIN_SENHA` estão vazios. Na subida, se ainda não existir senha para esse e-mail, o processo cria o master sozinho. Também dá para rodar:

```
flask criar-super-admin
```

Esse acesso é o administrador master: entra em todas as áreas e cadastra a equipe. Troque a senha no painel, em Equipe, depois do primeiro acesso.

Se `ADMIN_EMAIL` ou `ADMIN_SENHA` estiverem preenchidos no `.env`, o comando usa esses valores. Rodar de novo sem `ADMIN_SENHA` não troca uma senha que já existe.

## 3. Variáveis novas

Copie de `env.exemplo` para o `.env`, se essas linhas ainda não existirem:

```
ADMIN_EMAIL=
ADMIN_SENHA=
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```

`ADMIN_EMAIL` e `ADMIN_SENHA` são opcionais. Servem para o comando `flask criar-super-admin`.

`WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID` são opcionais. Ficam reservadas para a API oficial da Meta. Com elas vazias, o painel não envia mensagem à Meta. O WhatsApp continua abrindo a conversa pelo link `wa.me`, e o e-mail continua no Brevo.

As variáveis que já existiam (`DATABASE_URL`, `SECRET_KEY`, Brevo, Supabase) não mudaram de nome. O Supabase segue para o banco e para as imagens. Ele não autentica mais o painel.

## 4. Equipe e permissões

No painel, a aba Equipe (só o administrador master) cadastra e-mail, senha e ministério. Cada caixa marcada libera uma área:

| Código | O que libera |
| --- | --- |
| `gerenciar_fotos` | Fotos dos informativos |
| `criar_informativos` | Banners, fotos, vídeos e avisos |
| `gerenciar_eventos` | Qualquer evento |
| `gerenciar_eventos_empreendedores` | Só eventos do Ministério de Empreendedores |
| `divulgar_empreendedores` | Preparar WhatsApp, sem o e-mail geral |
| `enviar_comunicados` | E-mail e WhatsApp |
| `gerenciar_congregados` | Lista, edição e CSV |
| `gerenciar_campanhas` | Campanhas |
| `gerenciar_subsedes` | Subsede e sede |
| `gerenciar_feriados` | Feriados locais |
| `gerenciar_configuracoes` | Textos e redes do site |

O menu e as rotas usam a mesma lista. Um acesso sem a permissão não vê o botão e, se chamar o endereço, volta ao painel.

## 5. Congregados e remoção de dados

O formulário público continua em `/congregado`, sem login. O consentimento é obrigatório. O WhatsApp pede DDD + número e é gravado também como `55` + DDD + número.

A página pública fica no rodapé: **Descadastrar / Remoção de Dados ou alteração cadastral (LGPD)**, no endereço `/lgpd`. O pedido pede o e-mail e o WhatsApp do cadastro, juntos. Se os dois conferem, a remoção apaga nome, e-mail e telefone na hora (o registro vira "Cadastro removido"). A alteração cadastral não apaga nada: o painel mostra o pedido e o botão Editar abre o cadastro para a equipe corrigir nome, e-mail, WhatsApp e subsede. Ao salvar, o pedido pendente fica como alteração feita. O pedido guarda só o hash dos identificadores, a data e o texto.

O link antigo do e-mail (`/descadastrar/<token>`) continua só interrompendo os envios, sem apagar o cadastro. Dessa tela dá para ir à remoção completa.
