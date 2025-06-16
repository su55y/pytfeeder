package models

import "time"

type Entry struct {
	Id        string
	Title     string
	Published time.Time
	ChannelId string
	IsViewed  bool
	IsDeleted bool
}

type Channel struct {
	Id          string `yaml:"channel_id"`
	Title       string `yaml:"title"`
	HaveUpdates bool
	Hidden      bool `yaml:"hidden"`
	Total       int
	Unwatched   int
}
