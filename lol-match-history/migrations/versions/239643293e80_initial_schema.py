"""initial schema

Revision ID: 239643293e80
Revises: 
Create Date: 2026-11-21 16:54:15.027646

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '239643293e80'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

    op.create_table(
        'matches',
        sa.Column('match_id', sa.String(length=32), nullable=False),
        sa.Column('region', sa.String(length=10), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('game_creation', sa.BigInteger(), nullable=False),
        sa.Column('game_duration', sa.Integer(), nullable=False),
        sa.Column('patch_version', sa.String(length=16), nullable=False),
        sa.Column('winning_team_id', sa.SmallInteger(), nullable=False),
        sa.Column('teams_jsonb', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('match_id'),
    )
    op.create_table(
        'players',
        sa.Column('puuid', sa.String(length=78), nullable=False),
        sa.Column('region', sa.String(length=10), nullable=False),
        sa.Column('game_name', sa.String(length=64), nullable=False),
        sa.Column('tag_line', sa.String(length=16), nullable=False),
        sa.Column('profile_icon_id', sa.Integer(), nullable=True),
        sa.Column('summoner_level', sa.Integer(), nullable=True),
        sa.Column('solo_tier', sa.String(length=16), nullable=True),
        sa.Column('solo_rank', sa.String(length=8), nullable=True),
        sa.Column('solo_lp', sa.Integer(), server_default='0', nullable=False),
        sa.Column('solo_wins', sa.Integer(), server_default='0', nullable=False),
        sa.Column('solo_losses', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('puuid'),
    )
    op.create_index(
        'idx_players_riotid',
        'players',
        ['region', sa.text('lower(game_name)'), sa.text('lower(tag_line)')],
        unique=False,
    )
    op.create_table(
        'static_assets',
        sa.Column('patch_version', sa.String(length=16), nullable=False),
        sa.Column('lang', sa.String(length=10), server_default='vi_VN', nullable=False),
        sa.Column('champions_jsonb', json_type, nullable=False),
        sa.Column('items_jsonb', json_type, nullable=False),
        sa.Column('runes_jsonb', json_type, nullable=False),
        sa.Column('spells_jsonb', json_type, nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('patch_version', 'lang'),
    )
    op.create_table(
        'match_participants',
        sa.Column('match_id', sa.String(length=32), nullable=False),
        sa.Column('puuid', sa.String(length=78), nullable=False),
        sa.Column('riot_id_name', sa.String(length=64), nullable=True),
        sa.Column('riot_id_tagline', sa.String(length=16), nullable=True),
        sa.Column('team_id', sa.SmallInteger(), nullable=False),
        sa.Column('team_position', sa.String(length=16), nullable=True),
        sa.Column('champion_id', sa.Integer(), nullable=False),
        sa.Column('win', sa.Boolean(), nullable=False),
        sa.Column('kills', sa.SmallInteger(), nullable=False),
        sa.Column('deaths', sa.SmallInteger(), nullable=False),
        sa.Column('assists', sa.SmallInteger(), nullable=False),
        sa.Column('cs_total', sa.SmallInteger(), nullable=False),
        sa.Column('gold_earned', sa.Integer(), nullable=False),
        sa.Column('damage_to_champs', sa.Integer(), nullable=False),
        sa.Column('vision_score', sa.SmallInteger(), nullable=False),
        sa.Column('items_jsonb', json_type, nullable=False),
        sa.Column('runes_jsonb', json_type, nullable=False),
        sa.Column('spells_jsonb', json_type, nullable=False),
        sa.Column('game_creation', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('match_id', 'puuid'),
    )
    op.create_index('idx_mp_puuid_champ', 'match_participants', ['puuid', 'champion_id'], unique=False)
    op.create_index(
        'idx_mp_puuid_gc_match',
        'match_participants',
        ['puuid', sa.text('game_creation DESC'), sa.text('match_id DESC')],
        unique=False,
    )
    op.create_index(
        'idx_mp_puuid_recent',
        'match_participants',
        ['puuid', sa.text('game_creation DESC')],
        unique=False,
    )

    op.create_table(
        'match_timelines',
        sa.Column('match_id', sa.String(length=32), nullable=False),
        sa.Column('interval_ms', sa.Integer(), server_default='60000', nullable=False),
        sa.Column('frames_jsonb', json_type, nullable=False),
        sa.Column('events_jsonb', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('match_id'),
    )


def downgrade():
    op.drop_table('match_timelines')
    op.drop_index('idx_mp_puuid_recent', table_name='match_participants')
    op.drop_index('idx_mp_puuid_gc_match', table_name='match_participants')
    op.drop_index('idx_mp_puuid_champ', table_name='match_participants')
    op.drop_table('match_participants')
    op.drop_table('static_assets')
    op.drop_index('idx_players_riotid', table_name='players')
    op.drop_table('players')
    op.drop_table('matches')
