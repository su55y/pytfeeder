package config

import (
	"fmt"
	"os"
	"path/filepath"
)

const (
	pytfeeder    = "pytfeeder"
	configYaml   = "config.yaml"
	channelsYaml = "channels.yaml"
	StorageName  = "pytfeeder.db"
)

func DefaultConfigPath() string {
	return filepath.Join(configDir(), pytfeeder, configYaml)
}

func defaultChannelsPath() string {
	return filepath.Join(configDir(), pytfeeder, channelsYaml)
}

func defaultStoragePath() string {
	return filepath.Join(defaultDataDir(), StorageName)
}

func homeDir() string {
	homePath, err := os.UserHomeDir()
	if err != nil {
		fmt.Printf("ERR: Can't get home dir: %v\n", err)
		os.Exit(1)
	}
	return homePath
}

func configDir() string {
	configHome := os.Getenv("XDG_CONFIG_HOME")
	if configHome == "" {
		configHome = filepath.Join(homeDir(), ".config")
	}
	return configHome
}

func defaultDataDir() string {
	dataHome := os.Getenv("XDG_DATA_HOME")
	if dataHome == "" {
		dataHome = filepath.Join(homeDir(), ".local", "share")
	}
	return dataHome
}
