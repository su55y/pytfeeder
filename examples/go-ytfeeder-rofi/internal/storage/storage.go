package storage

import (
	"database/sql"
	"fmt"
	"strings"

	"github.com/su55y/pytfeeder/examples/go-ytfeeder-rofi/internal/models"
)

type Storage struct {
	db *sql.DB
}

func NewStorage(path string) *Storage {
	return &Storage{db: GetDB(path)}
}

func (s *Storage) SelectFeedEntries(limit int) ([]models.Entry, error) {
	stmt := `
	SELECT id, title, published, channel_id, is_viewed, is_deleted
	FROM tb_entries WHERE is_deleted = 0
	ORDER BY published DESC LIMIT ?`
	rows, err := s.db.Query(stmt, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []models.Entry
	for rows.Next() {
		var e models.Entry
		if err := rows.Scan(&e.Id, &e.Title, &e.Published, &e.ChannelId, &e.IsViewed, &e.IsDeleted); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}

	return entries, nil
}

func (s *Storage) SelectChannelEntries(
	channelId string,
	unwatchedFirst bool,
	limit int,
) ([]models.Entry, error) {
	order := "published"
	if unwatchedFirst {
		order = "is_viewed, published"
	}
	stmt := fmt.Sprintf(`
	SELECT id, title, published, channel_id, is_viewed, is_deleted
	FROM tb_entries WHERE is_deleted = 0 AND channel_id = ?
	ORDER BY %s DESC LIMIT ?`, order)

	rows, err := s.db.Query(stmt, channelId, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []models.Entry
	for rows.Next() {
		var e models.Entry
		if err := rows.Scan(&e.Id, &e.Title, &e.Published, &e.ChannelId, &e.IsViewed, &e.IsDeleted); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}

	return entries, nil
}

func (s *Storage) SelectChannelsStats(channelsMap map[string]*models.Channel) error {
	stmt := `
	SELECT channel_id, SUM(is_deleted = 0 AND is_viewed = 0), SUM(is_deleted = 0) as c
	FROM tb_entries WHERE is_deleted = 0
	GROUP BY channel_id
	ORDER BY c DESC`
	rows, err := s.db.Query(stmt)
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var channelId string
		var unwatched, total int
		if err := rows.Scan(&channelId, &unwatched, &total); err != nil {
			return err
		}
		if c, ok := channelsMap[channelId]; ok {
			channelsMap[channelId].Unwatched = unwatched
			channelsMap[channelId].Total = total
			channelsMap[channelId].HaveUpdates = c.Unwatched > 0
		}
	}

	return nil
}

func (s *Storage) SelectFeedStats(feedChannel *models.Channel, channels []models.Channel) error {
	placeholders := make([]string, len(channels))
	args := make([]any, len(channels))
	for i := range channels {
		placeholders[i] = "?"
		args[i] = channels[i].Id
	}
	query := fmt.Sprintf(`
	SELECT SUM(is_deleted = 0 AND is_viewed = 0), SUM(is_deleted = 0)
	FROM tb_entries WHERE is_deleted = 0 AND channel_id in (%s)`,
		strings.Join(placeholders, ","))

	stmt, err := s.db.Prepare(query)
	if err != nil {
		return err
	}

	defer stmt.Close()

	row := stmt.QueryRow(args...)
	if err := row.Scan(&feedChannel.Unwatched, &feedChannel.Total); err != nil {
		return err
	}
	feedChannel.HaveUpdates = feedChannel.Unwatched > 0

	return nil
}
