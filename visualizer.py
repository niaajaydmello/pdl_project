import matplotlib.pyplot as plt
import networkx as nx


class GraphVisualizer:
    @staticmethod
    def draw_colored_graph(graph: nx.Graph, color_map: dict):
        """Draws the Graph network where node colors represent assigned time slots."""
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.patch.set_facecolor('#1a1a1a')
        ax.set_facecolor('#1a1a1a')

        # Generate colors dynamically based on slot IDs
        unique_colors = len(set(color_map.values())) if color_map else 1
        cmap = plt.cm.get_cmap('tab10', max(unique_colors, 1))

        node_colors = [cmap(color_map.get(node, 0)) for node in graph.nodes()]

        pos = nx.spring_layout(graph, seed=42)  # Consistent position layout

        # Draw edges
        nx.draw_networkx_edges(graph, pos, ax=ax, edge_color='#555555', width=1.5, alpha=0.7)

        # Draw nodes
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=node_colors, node_size=1200, edgecolors='white', linewidths=1.5)

        # Draw labels
        nx.draw_networkx_labels(graph, pos, ax=ax, font_color='white', font_family='sans-serif', font_weight='bold', font_size=10)

        ax.set_title("Conflict Graph (Colors = Time Slots)", color="white", fontsize=14, fontweight="bold", pad=12)
        plt.tight_layout()
        return fig