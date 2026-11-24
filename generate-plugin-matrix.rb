#!/usr/bin/env ruby
# frozen_string_literal: true

#
# Generate a matrix of Logstash plugins and which Logstash releases they ship in.
#
# Reads logstash-versions.yml for the current release versions, then for each
# release fetches the Gemfile lock file from the corresponding Logstash branch
# on GitHub and extracts the bundled plugins and their versions.
#
# Outputs YAML with:
#   supported-plugins: list of all unique plugin names across all versions
#   <logstash-version>: list of plugins with their versions for that release
#
# Usage:
#   ruby generate-plugin-matrix.rb [-o bundled-plugins.yml]
#
# Set GITHUB_TOKEN env var to avoid API rate limits.
#

require "net/http"
require "uri"
require "json"
require "optparse"

SCRIPT_DIR = File.dirname(File.expand_path(__FILE__))
VERSIONS_FILE = File.join(SCRIPT_DIR, "logstash-versions.yml")
GITHUB_REPO = "elastic/logstash"

# --- GitHub helpers ---

def github_get(path)
  uri = URI("https://api.github.com#{path}")
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true

  request = Net::HTTP::Get.new(uri)
  request["Accept"] = "application/vnd.github.v3+json"
  request["User-Agent"] = "logstash-plugin-matrix"
  token = ENV["GITHUB_TOKEN"]
  request["Authorization"] = "token #{token}" if token && !token.empty?

  response = http.request(request)
  raise "GitHub API error #{response.code} for #{path}: #{response.body[0..200]}" unless response.is_a?(Net::HTTPSuccess)

  response
end

def github_raw(branch, filepath)
  uri = URI("https://raw.githubusercontent.com/#{GITHUB_REPO}/#{branch}/#{filepath}")
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true

  request = Net::HTTP::Get.new(uri)
  request["User-Agent"] = "logstash-plugin-matrix"
  token = ENV["GITHUB_TOKEN"]
  request["Authorization"] = "token #{token}" if token && !token.empty?

  response = http.request(request)
  return nil unless response.is_a?(Net::HTTPSuccess)

  response.body
end

def find_lockfile_name(branch)
  resp = github_get("/repos/#{GITHUB_REPO}/contents/?ref=#{branch}")
  entries = JSON.parse(resp.body)
  entry = entries.find { |e| e["name"].start_with?("Gemfile.jruby-") && e["name"].end_with?(".lock.release") }
  entry&.dig("name")
end

# --- YAML parser (simple, no gem dependency) ---

def parse_versions_yaml(path)
  releases = {}
  in_releases = false

  File.readlines(path).each do |line|
    stripped = line.strip

    if stripped.start_with?("releases:")
      in_releases = true
      next
    end

    if in_releases
      if stripped.empty? || (!line.start_with?(" ") && !line.start_with?("\t"))
        in_releases = false
        next
      end

      if (m = line.match(/\s+(\S+):\s+"?([^"]+)"?/))
        releases[m[1]] = m[2].strip
      end
    end
  end

  releases
end

# --- Lock file parser ---

def parse_lockfile_plugins(content)
  plugins = {}
  in_gem = false
  in_specs = false

  content.each_line do |line|
    line.chomp!

    if line == "GEM"
      in_gem = true
      in_specs = false
      next
    end

    if in_gem && line.strip == "specs:"
      in_specs = true
      next
    end

    if in_gem && !line.empty? && !line.start_with?(" ")
      in_gem = false
      in_specs = false
      next
    end

    next unless in_specs

    # Top-level gems: exactly 4 spaces indent
    if (m = line.match(/^    (\S+) \(([^)]+)\)$/))
      name = m[1]
      version = m[2].sub(/-java$/, "")
      if name.start_with?("logstash-") && !name.start_with?("logstash-core")
        plugins[name] = version
      end
    end
  end

  plugins
end

# --- Main ---

def version_to_branch(version)
  parts = version.split(".")
  "#{parts[0]}.#{parts[1]}"
end

options = {}
OptionParser.new do |opts|
  opts.banner = "Usage: #{$PROGRAM_NAME} [options]"
  opts.on("-o", "--output FILE", "Output CSV file (default: stdout)") { |f| options[:output] = f }
  opts.on("--versions-file FILE", "Path to logstash-versions.yml") { |f| options[:versions_file] = f }
  opts.on("-h", "--help", "Show help") { puts opts; exit }
end.parse!

versions_file = options[:versions_file] || VERSIONS_FILE
releases = parse_versions_yaml(versions_file)

if releases.empty?
  warn "ERROR: No releases found in #{versions_file}"
  exit 1
end

# Deduplicate and sort
version_list = releases.values.uniq.sort_by { |v| v.split(".").map(&:to_i) }
warn "Releases: #{version_list.join(', ')}"

# Build per-version plugin lists: { ls_version => { plugin_name => plugin_version } }
version_plugins = {}

version_list.each do |ls_version|
  branch = version_to_branch(ls_version)
  warn "  #{ls_version} -> branch #{branch}"

  lockfile_name = find_lockfile_name(branch)
  unless lockfile_name
    warn "    WARNING: no lock file found on #{branch}"
    next
  end
  warn "    lock file: #{lockfile_name}"

  content = github_raw(branch, lockfile_name)
  unless content
    warn "    WARNING: could not fetch #{lockfile_name} from #{branch}"
    next
  end

  plugins = parse_lockfile_plugins(content)
  warn "    found #{plugins.size} plugins"
  version_plugins[ls_version] = plugins
end

# Collect all unique plugin names
all_plugins = version_plugins.values.flat_map(&:keys).uniq.sort

# Compute branches for each plugin based on major version spread.
# Highest major -> "main", others -> "<major>.x"
plugin_branches = {}
all_plugins.each do |plugin_name|
  majors = version_plugins.values
    .filter_map { |plugins| plugins[plugin_name]&.split(".")&.first&.to_i }
    .uniq
    .sort

  max_major = majors.max
  branches = majors.map { |m| m == max_major ? "main" : "#{m}.x" }
  plugin_branches[plugin_name] = branches
end

# Output YAML (hand-written to avoid dependency and keep it clean)
out = options[:output] ? File.open(options[:output], "w") : $stdout

out.puts "# Auto-generated by generate-plugin-matrix.rb"
out.puts "# Lists all Logstash plugins bundled with each release"
out.puts "#"
out.puts "# supported-plugins: union of all plugins across all tracked releases"
out.puts "#   branches: 'main' for the latest major version, '<major>.x' for older"
out.puts "# <version>: plugins shipped in that Logstash release"
out.puts

out.puts "supported-plugins:"
all_plugins.each do |p|
  branches = plugin_branches[p]
  out.puts "  - name: #{p}"
  out.puts "    branches:"
  branches.each { |b| out.puts "      - #{b}" }
end

version_list.each do |ls_version|
  plugins = version_plugins[ls_version]
  next unless plugins

  out.puts
  out.puts "#{ls_version}:"
  plugins.keys.sort.each do |name|
    out.puts "  #{name}: \"#{plugins[name]}\""
  end
end

if options[:output]
  out.close
  warn "\nWrote #{options[:output]}"
end
