package config

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	yaml "gopkg.in/yaml.v3"

	"github.com/su55y/pytfeeder/examples/go-ytfeeder-rofi/internal/models"
)

const (
	DefaultChannelsFmt    = "{title}\000info\037{id}\037active\037{active}"
	DefaultEntriesFmt     = "{title}\000info\037{id}\037active\037{active}"
	DefaultFeedEntriesFmt = "{title}\000info\037{id}\037active\037{active}"
	DefaultDatetimeFmt    = "%b %d"
)

func defaultSeparator() yaml.Node {
	return yaml.Node{
		Kind:  yaml.ScalarNode,
		Tag:   "!!str",
		Value: "\n",
		Style: yaml.DoubleQuotedStyle,
	}
}

type RofiConfig struct {
	AlphabeticSort   bool      `yaml:"alphabetic_sort"`
	ChannelFeedLimit int       `yaml:"channel_feed_limit"`
	ChannelsFmt      string    `yaml:"channels_fmt"`
	DatetimeFmt      string    `yaml:"datetime_fmt"`
	EntriesFmt       string    `yaml:"entries_fmt"`
	FeedEntriesFmt   string    `yaml:"feed_entries_fmt"`
	FeedLimit        int       `yaml:"feed_limit"`
	HideEmpty        bool      `yaml:"hide_empty"`
	HideFeed         bool      `yaml:"hide_feed"`
	Separator        yaml.Node `yaml:"separator"`
	UnwatchedFirst   bool      `yaml:"unwatched_first"`
}

type Config struct {
	ChannelsPath string `yaml:"channels_filepath"`
	DataDir      string `yaml:"data_dir"`
	StorageFile  string `yaml:"-"`
	RofiConfig   `yaml:"rofi"`
}

func defaultConfig() Config {
	return Config{
		defaultChannelsPath(),
		defaultDataDir(),
		defaultStoragePath(),
		RofiConfig{
			ChannelFeedLimit: -1,
			ChannelsFmt:      DefaultChannelsFmt,
			DatetimeFmt:      DefaultDatetimeFmt,
			EntriesFmt:       DefaultEntriesFmt,
			FeedEntriesFmt:   DefaultFeedEntriesFmt,
			FeedLimit:        -1,
			Separator:        defaultSeparator(),
		},
	}
}

func GetConfig(path string) Config {
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		fmt.Printf("ERR: Config not found at %s\n", path)
		return defaultConfig()
	} else if err != nil {
		fmt.Printf("ERR: %v\n", err)
		os.Exit(1)
	}

	file, err := os.OpenFile(path, os.O_RDONLY, 0644)
	if err != nil {
		fmt.Printf("ERR: Opening config: %v (%s)", err, path)
	}
	var c Config
	if err := yaml.NewDecoder(file).Decode(&c); err != nil {
		fmt.Printf("ERR: Decoding config: %s (%s)\n", err.Error(), path)
		os.Exit(1)
	}

	if c.ChannelsFmt == "" {
		c.ChannelsFmt = DefaultChannelsFmt
	}

	if c.DatetimeFmt == "" {
		c.DatetimeFmt = DefaultDatetimeFmt
	}

	if c.EntriesFmt == "" {
		c.EntriesFmt = DefaultEntriesFmt
	}

	if c.FeedEntriesFmt == "" {
		c.FeedEntriesFmt = DefaultFeedEntriesFmt
	}

	if c.Separator.Value == "" {
		c.Separator = defaultSeparator()
	}

	if strings.HasPrefix(c.ChannelsPath, "~/") {
		c.ChannelsPath = filepath.Join(homeDir(), c.ChannelsPath[1:])
	}

	if strings.HasPrefix(c.DataDir, "~/") {
		c.DataDir = filepath.Join(homeDir(), c.DataDir[1:])
	}

	c.StorageFile = filepath.Join(c.DataDir, StorageName)

	return c
}

func LoadChannels(path string) []models.Channel {
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		fmt.Printf("ERR: Channels file not found at %s\n", path)
		return []models.Channel{}
	} else if err != nil {
		fmt.Printf("ERR: %v\n", err)
		os.Exit(1)
	}

	file, err := os.OpenFile(path, os.O_RDONLY, 0644)
	if err != nil {
		fmt.Printf("ERR: Opening channels file: %v (%s)", err, path)
	}
	var channels []models.Channel
	if err := yaml.NewDecoder(file).Decode(&channels); err != nil {
		fmt.Printf("ERR: Decoding channels file: %s (%s)\n", err.Error(), path)
		os.Exit(1)
	}
	i := 0
	for _, c := range channels {
		if !c.Hidden {
			channels[i] = c
			i++
		}
	}
	return channels[:i]
}

func (c *Config) Print() {
	dump, err := yaml.Marshal(c)
	if err != nil {
		fmt.Printf("Error while marshaling: %v\n", err)
		return
	}
	fmt.Print(string(dump))
}
